import time
import requests
import streamlit as st
from datetime import datetime
from typing import Any, Dict, List, Tuple

STATE_URL = "http://127.0.0.1:8765/state"
CHOOSE_URL = "http://127.0.0.1:8765/choose_agenda"

st.set_page_config(page_title="Live Meeting", layout="wide")

CSS = """
<style>
:root {
  --bg: #0f1115;
  --card: #171a21;
  --text: #f9fafb;
  --muted: #9ca3af;
  --border: #222734;
  --accent: #22c55e;
  --accent-soft: #0f2a1a;
  --danger: #ef4444;
  --chip: #1f2430;
}

html, body, [data-testid="stAppViewContainer"] {
  background: var(--bg);
  color: var(--text);
}

.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 14px 16px;
  margin-bottom: 12px;
  box-shadow: 0 10px 24px rgba(0,0,0,0.25);
}

.card h4 {
  margin: 0 0 8px 0;
  font-size: 0.95rem;
  color: var(--text);
}

.muted {
  color: var(--muted);
  font-size: 0.85rem;
}

.badge-live {
  background: var(--accent-soft);
  color: var(--accent);
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
}

.badge-off {
  background: #3a1a1a;
  color: var(--danger);
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
}

.divider {
  height: 1px;
  background: var(--border);
  margin: 10px 0 12px 0;
}

.list-item {
  padding: 6px 0;
  border-bottom: 1px dashed #eef0f4;
}

.list-item:last-child {
  border-bottom: none;
}

.topbar {
  background: #0b0d12;
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 12px 16px;
  margin-bottom: 12px;
  box-shadow: 0 12px 28px rgba(0,0,0,0.3);
}

.chip {
  display: inline-block;
  background: var(--chip);
  color: var(--muted);
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 0.75rem;
  margin-right: 6px;
}

.panel-title {
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--muted);
  margin-bottom: 8px;
}

.stage {
  background: linear-gradient(145deg, #141821, #0f1115);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 12px;
  min-height: 120px;
}
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)


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


def fetch_state() -> Dict[str, Any]:
    r = requests.get(STATE_URL, timeout=1.5)
    r.raise_for_status()
    return r.json()


def choose_agenda(title: str) -> Dict[str, Any]:
    r = requests.post(CHOOSE_URL, json={"title": title}, timeout=2.0)
    r.raise_for_status()
    return r.json()


def safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def latest_summary(timeline: List[Dict[str, Any]]) -> str:
    if timeline:
        last = timeline[-1].get("text")
        if last:
            return last
    return "요약 생성 대기 중…"


def extract_signals(tail: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    decisions = []
    tasks = []
    ideas = []
    issues = []
    questions = []

    decision_kw = ("결정", "확정", "이걸로", "결론", "채택", "최종", "합의", "정하자")
    task_kw = ("할게", "하겠습니다", "담당", "까지", "해야", "진행", "액션", "요청")
    idea_kw = ("아이디어", "대안", "제안", "옵션", "해보자")
    issue_kw = ("문제", "리스크", "우려", "막힘", "지연", "오류")
    question_kw = ("질문", "궁금", "확인 필요")

    for item in tail:
        text = (item.get("text") or "").strip()
        if not text:
            continue

        lower = text
        entry = {
            "t": item.get("t"),
            "speaker": item.get("speaker", ""),
            "text": text,
        }

        if any(k in lower for k in decision_kw):
            decisions.append(entry)
        if any(k in lower for k in task_kw):
            tasks.append(entry)
        if any(k in lower for k in idea_kw):
            ideas.append(entry)
        if any(k in lower for k in issue_kw):
            issues.append(entry)
        if "?" in lower or any(k in lower for k in question_kw):
            questions.append(entry)

    return {
        "decisions": decisions,
        "tasks": tasks,
        "ideas": ideas,
        "issues": issues,
        "questions": questions,
    }


def group_by_speaker(tail: List[Dict[str, Any]], limit: int = 3) -> List[Tuple[str, List[str]]]:
    buckets: Dict[str, List[str]] = {}
    for item in tail:
        spk = item.get("speaker", "Unknown") or "Unknown"
        text = (item.get("text") or "").strip()
        if not text:
            continue
        buckets.setdefault(spk, []).append(text)
    out = []
    for spk, texts in buckets.items():
        out.append((spk, texts[-limit:]))
    out.sort(key=lambda x: (-len(x[1]), x[0]))
    return out


if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = True
if "refresh_sec" not in st.session_state:
    st.session_state.refresh_sec = 2
if "paused" not in st.session_state:
    st.session_state.paused = False

with st.sidebar:
    st.markdown("### Navigation")
    st.radio("", ["Live", "Transcript", "Agenda", "Assistant", "Settings"], index=0)
    st.markdown("---")
    st.session_state.refresh_sec = st.slider("Refresh (sec)", 1, 10, st.session_state.refresh_sec)
    st.session_state.auto_refresh = st.checkbox("Auto refresh", value=st.session_state.auto_refresh)

try:
    data = fetch_state()
    connected = True
except Exception as e:
    data = {"error": str(e)}
    connected = False

# Top bar (Google Meets-like)
st.markdown("<div class='topbar'>", unsafe_allow_html=True)
col_a, col_b, col_c, col_d = st.columns([6, 2, 2, 2])
with col_a:
    st.markdown("## Live Meeting")
    st.markdown("<span class='chip'>Meeting room</span><span class='chip'>Enterprise</span>", unsafe_allow_html=True)
with col_b:
    st.markdown("<span class='badge-live'>LIVE</span>" if connected else "<span class='badge-off'>OFFLINE</span>", unsafe_allow_html=True)
with col_c:
    st.markdown(f"<span class='chip'>{datetime.now().strftime('%H:%M')}</span>", unsafe_allow_html=True)
with col_d:
    if st.button("Stop" if not st.session_state.paused else "Start", use_container_width=True):
        st.session_state.paused = not st.session_state.paused
        if st.session_state.paused:
            st.session_state.auto_refresh = False
        st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

if not connected:
    st.error(f"State server unavailable: {data.get('error')}")
    st.stop()

# Main layout
left, center, right = st.columns([4, 4, 3])

# Left column: transcript & summary
with left:
    timeline = safe_list(data.get("progress_timeline"))
    tail = safe_list(data.get("recent_tail"))
    signals = extract_signals(tail)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title'>Transcript Summary</div>", unsafe_allow_html=True)
    st.write(latest_summary(timeline))
    if timeline:
        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
        for item in timeline[-6:]:
            st.write(f"[{fmt_ts(item.get('ts'))}] {item.get('text','')}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title'>Transcript</div>", unsafe_allow_html=True)
    preview = safe_list(data.get("meeting_text_tail_preview"))
    if preview:
        for line in preview[-40:]:
            st.write(line)
    else:
        if not tail:
            st.markdown("<span class='muted'>전사 데이터 없음</span>", unsafe_allow_html=True)
        for item in tail[-40:]:
            st.write(f"[{fmt_ts(item.get('t'))}] [{item.get('speaker','')}] {item.get('text','')}")
    st.markdown("</div>", unsafe_allow_html=True)

# Center column: agenda / opinions / suggestions
with center:
    current_agenda = safe_dict(data.get("current_agenda"))
    pending_candidates = safe_list(data.get("pending_agenda_candidates"))

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title'>Current Agenda</div>", unsafe_allow_html=True)
    if current_agenda:
        st.write(current_agenda.get("title", ""))
        st.markdown(f"<span class='muted'>시작: {fmt_ts(current_agenda.get('started_at'))}</span>", unsafe_allow_html=True)
        if current_agenda.get("ended_at"):
            st.markdown(f"<br><span class='muted'>종료: {fmt_ts(current_agenda.get('ended_at'))}</span>", unsafe_allow_html=True)
        if current_agenda.get("status"):
            st.markdown(f"<br><span class='muted'>상태: {current_agenda.get('status')}</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span class='muted'>아직 안건이 선택되지 않았습니다.</span>", unsafe_allow_html=True)

    if pending_candidates and not current_agenda:
        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
        st.write("안건 선택")
        cols = st.columns(3)
        for i in range(3):
            title = pending_candidates[i] if len(pending_candidates) > i else None
            with cols[i]:
                if title:
                    if st.button(title, key=f"agenda_btn_{i}", use_container_width=True):
                        try:
                            choose_agenda(title)
                            st.success(f"안건 선택됨: {title}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"안건 선택 전송 실패: {e}")
                else:
                    st.button("—", disabled=True, use_container_width=True)
    if signals["decisions"] or signals["tasks"]:
        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
        if signals["decisions"]:
            st.markdown("**Decisions in progress**")
            for item in signals["decisions"][-3:]:
                st.markdown(f"- {item.get('text','')}")
        if signals["tasks"]:
            st.markdown("**Action candidates**")
            for item in signals["tasks"][-3:]:
                spk = item.get("speaker", "")
                txt = item.get("text", "")
                if spk:
                    st.markdown(f"- {spk}: {txt}")
                else:
                    st.markdown(f"- {txt}")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title'>Opinion Comparison</div>", unsafe_allow_html=True)
    speaker_groups = group_by_speaker(tail, limit=2)
    if speaker_groups:
        for spk, texts in speaker_groups[:6]:
            st.markdown(f"**{spk}**")
            for t in texts:
                st.markdown(f"- {t}")
    else:
        st.markdown("<span class='muted'>의견 비교 데이터 없음</span>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title'>AI Suggestions</div>", unsafe_allow_html=True)
    if pending_candidates:
        for item in pending_candidates[:3]:
            st.markdown(f"- {item}")
    elif signals["issues"] or signals["questions"]:
        for item in signals["issues"][-2:]:
            st.markdown(f"- 리스크: {item.get('text','')}")
        for item in signals["questions"][-2:]:
            st.markdown(f"- 확인 필요: {item.get('text','')}")
    else:
        st.markdown("<span class='muted'>제안 데이터 없음</span>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# Right column: assistant panel
with right:
    st.markdown("<div class='stage'>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title'>AI Assistant</div>", unsafe_allow_html=True)
    st.markdown("<span class='muted'>회의 중 의사결정 지원</span>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    decision_log = safe_list(data.get("decision_log"))

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title'>Ideas</div>", unsafe_allow_html=True)
    if signals["ideas"]:
        for item in signals["ideas"][-5:]:
            st.markdown(f"- {item.get('text','')}")
    elif signals["issues"]:
        for item in signals["issues"][-3:]:
            st.markdown(f"- {item.get('text','')}")
    else:
        st.markdown("<span class='muted'>아이디어 없음</span>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title'>Options</div>", unsafe_allow_html=True)
    if pending_candidates:
        for item in pending_candidates[:5]:
            st.markdown(f"- {item}")
    elif signals["questions"]:
        for item in signals["questions"][-5:]:
            st.markdown(f"- {item.get('text','')}")
    else:
        st.markdown("<span class='muted'>옵션 없음</span>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title'>Live Action Candidates</div>", unsafe_allow_html=True)
    if decision_log:
        for d in decision_log[-5:]:
            spk = d.get("speaker", "")
            txt = d.get("text", "")
            st.markdown(f"- {spk}: {txt}")
    elif signals["tasks"]:
        for item in signals["tasks"][-5:]:
            spk = item.get("speaker", "")
            txt = item.get("text", "")
            st.markdown(f"- {spk}: {txt}")
    elif signals["decisions"]:
        for item in signals["decisions"][-5:]:
            st.markdown(f"- {item.get('text','')}")
    else:
        st.markdown("<span class='muted'>액션 후보 없음</span>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.auto_refresh and not st.session_state.paused:
    time.sleep(st.session_state.refresh_sec)
    st.rerun()
