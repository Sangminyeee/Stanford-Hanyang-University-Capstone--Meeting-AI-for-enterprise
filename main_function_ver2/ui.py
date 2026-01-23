import time
import requests
import streamlit as st
from datetime import datetime

STATE_URL = "http://127.0.0.1:8765/state"
CHOOSE_URL = "http://127.0.0.1:8765/choose_agenda"

st.set_page_config(page_title="Meeting Flow Dashboard", layout="wide")
st.title("회의 흐름 대시보드 (F2 + F4)")

refresh_sec = st.sidebar.slider("갱신 주기(초)", 1, 10, 2)
auto = st.sidebar.checkbox("자동 갱신", value=True)

def fmt_ts(ts) -> str:
    if ts is None:
        return "--:--:--"
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts).strftime("%H:%M:%S")
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts).strftime("%H:%M:%S")
        except Exception:
            return ts
    return str(ts)

def progress_summary(data: dict) -> str:
    s = data.get("progress_summary")
    if s:
        return s
    timeline = data.get("progress_timeline") or []
    if timeline:
        last = timeline[-1].get("text")
        if last:
            return last
    return "요약 생성 대기 중…"

def fetch_state():
    r = requests.get(STATE_URL, timeout=1.5)
    r.raise_for_status()
    return r.json()

def choose_agenda(title: str):
    r = requests.post(CHOOSE_URL, json={"title": title}, timeout=2.0)
    r.raise_for_status()
    return r.json()

try:
    data = fetch_state()
except Exception as e:
    st.error(f"상태 서버 연결 실패: {e}")
    st.stop()

st.subheader("진행 요약")
st.write(progress_summary(data))
timeline = data.get("progress_timeline") or []
if timeline:
    with st.expander("타임라인", expanded=False):
        for item in timeline[-10:]:
            st.write(f"[{fmt_ts(item.get('ts'))}] {item.get('text','')}")
st.divider()

# 안건 선택 UI
pending_candidates = data.get("pending_agenda_candidates") or []
needs_choice = bool(pending_candidates) and not data.get("current_agenda")

if needs_choice:
    st.warning("안건 선택이 필요합니다.")
    cands = pending_candidates

    btn_titles = [
        cands[0] if len(cands) > 0 else None,
        cands[1] if len(cands) > 1 else None,
        cands[2] if len(cands) > 2 else None,
    ]

    col1, col2, col3 = st.columns(3)
    cols = [col1, col2, col3]

    chosen = None
    for i, (col, title) in enumerate(zip(cols, btn_titles), start=1):
        with col:
            if title:
                if st.button(title, key=f"agenda_btn_{i}", use_container_width=True):
                    chosen = title
            else:
                st.button("—", key=f"agenda_btn_empty_{i}", disabled=True, use_container_width=True)

    custom = st.text_input("또는 안건 직접 입력", value="")

    if chosen is not None:
        try:
            choose_agenda(chosen)
            st.success(f"안건 선택됨: {chosen}")
            st.rerun()
        except Exception as e:
            st.error(f"안건 선택 전송 실패: {e}")

        # 직접 입력을 쓰고 싶으면 "확정" 버튼 하나만 둠
    if st.button("직접 입력 안건 확정", type="primary"):
        title = custom.strip()
        if not title:
            st.error("직접 입력 안건 제목을 입력하세요.")
        else:
            try:
                choose_agenda(title)
                st.success(f"안건 선택됨: {title}")
                st.rerun()
            except Exception as e:
                st.error(f"안건 선택 전송 실패: {e}")

st.divider()

st.subheader("최근 전사")
tail_preview = data.get("meeting_text_tail_preview") or []
if tail_preview:
    for line in tail_preview:
        st.write(line)
else:
    tail = data.get("recent_tail") or []
    for x in tail[-40:]:
        st.write(f"[{fmt_ts(x.get('t'))}] [{x.get('speaker','')}] {x.get('text','')}")

ag = data.get("current_agenda")

st.subheader("결정 로그 (실시간)")
dlog = data.get("decision_log") or []

if not dlog:
    st.info("아직 감지된 결정이 없습니다.")
else:
    for d in reversed(dlog[-20:]):
        t = d.get("t", 0.0)
        spk = d.get("speaker", "")
        txt = d.get("text", "")
        agenda = d.get("agenda", "Unassigned")
        conf = d.get("confidence", None)

        header = f"[{fmt_ts(t)}] ({agenda}) {spk}: {txt}"
        if conf is not None:
            header += f"  (conf={conf:.2f})"

        with st.expander(header, expanded=False):
            ev = d.get("evidence") or []
            if not ev:
                st.write("근거 스니펫 없음")
            else:
                st.caption("근거(전후 발언)")
                for e in ev:
                    st.write(f"- [{fmt_ts(e.get('t', 0.0))}] [{e.get('speaker','')}] {e.get('text','')}")

col1, col2 = st.columns([1, 1])



with col1:
    st.subheader("현재 안건")
    if not ag:
        st.info("아직 안건이 선택되지 않았습니다.")
    else:
        st.markdown(f"### {ag.get('title','')}")
        st.caption(f"시작: {fmt_ts(ag.get('started_at'))}")
        if ag.get("ended_at"):
            st.caption(f"종료: {fmt_ts(ag.get('ended_at'))}")
        if ag.get("status"):
            st.write(f"상태: {ag.get('status')}")

with col2:
    st.subheader("안건 히스토리")
    history = data.get("agenda_history") or []
    if not history:
        st.write("히스토리 없음")
    else:
        for item in reversed(history[-10:]):
            title = item.get("title", "")
            status = item.get("status", "")
            started = fmt_ts(item.get("started_at"))
            ended = fmt_ts(item.get("ended_at")) if item.get("ended_at") else ""
            header = f"{title} ({status})"
            with st.expander(header, expanded=False):
                st.write(f"시작: {started}")
                if ended:
                    st.write(f"종료: {ended}")
                if item.get("summary"):
                    st.write(item.get("summary"))

st.divider()
st.subheader("최근 전사 (tail)")
tail = data.get("recent_tail") or []
for x in tail[-40:]:
    st.write(f"[{fmt_ts(x.get('t'))}] [{x.get('speaker','')}] {x.get('text','')}")

if auto:
    time.sleep(refresh_sec)
    st.rerun()
else:
    if st.button("지금 새로고침"):
        st.rerun()
