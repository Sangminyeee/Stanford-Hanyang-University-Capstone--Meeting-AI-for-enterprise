import time
import requests
import streamlit as st
from datetime import datetime

STATE_URL = "http://127.0.0.1:8765/state"

st.set_page_config(page_title="Meeting Flow Dashboard", layout="wide")
st.title("회의 흐름 대시보드 (F2 + F4)")

refresh = st.sidebar.slider("갱신 주기(초)", 0.5, 5.0, 1.0, 0.5)
auto = st.sidebar.checkbox("자동 갱신", value=True)

placeholder = st.empty()

def fmt_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")

while True:
    try:
        r = requests.get(STATE_URL, timeout=1.5)
        data = r.json()
    except Exception as e:
        placeholder.error(f"상태 서버 연결 실패: {e}")
        if not auto:
            break
        time.sleep(refresh)
        continue

    with placeholder.container():
        col1, col2 = st.columns([1, 1])

        ag = data.get("current_agenda")
        with col1:
            st.subheader("현재 안건")
            if not ag:
                st.info("아직 안건이 선택되지 않았습니다.")
            else:
                st.markdown(f"### {ag['title']}")
                st.caption(f"시작: {fmt_ts(ag['started_at'])}")
                st.write(ag.get("running_summary") or "")

                st.markdown("**결정**")
                st.write(ag.get("decisions") or [])

                st.markdown("**할일**")
                st.write(ag.get("todos") or [])

        with col2:
            st.subheader("의견(화자별)")
            if ag and ag.get("opinions_by_speaker"):
                for spk, ops in ag["opinions_by_speaker"].items():
                    with st.expander(spk, expanded=False):
                        for op in ops:
                            st.write(f"- {op}")
            else:
                st.write("의견 데이터 없음")

        st.divider()
        st.subheader("최근 전사 (tail)")
        tail = data.get("recent_tail") or []
        for x in tail[-30:]:
            st.write(f"[{fmt_ts(x['t'])}] [{x['speaker']}] {x['text']}")

    if not auto:
        break
    time.sleep(refresh)
    st.rerun()
