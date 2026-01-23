import time
import html
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

.chat ??? {
}

.chat-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chat-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.chat-meta {
  font-size: 0.72rem;
  color: var(--muted);
}

.chat-bubble {
  background: #1b2230;
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 10px 12px;
  line-height: 1.35;
}

.kw-chip {
  display: inline-block;
  background: #1f2a3a;
  color: #d1d5db;
  border: 1px solid var(--border);
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 0.72rem;
  margin: 4px 6px 0 0;
}

.metric {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--text);
}

.metric-label {
  font-size: 0.75rem;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
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
    return "?? ?? ?? ??"


def extract_signals(tail: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    decisions = []
    tasks = []
    ideas = []
    issues = []
    questions = []

    decision_kw = ("??", "??", "???", "??", "??", "??", "??", "???")
    task_kw = ("??", "?????", "??", "??", "??", "??", "??", "??")
    idea_kw = ("????", "??", "??", "??", "???")
    issue_kw = ("??", "???", "??", "??", "??", "??")
    question_kw = ("??", "??", "?? ??")

    for item in tail:
        text = (item.get("text") or "").strip()
        if not text:
            continue

        entry = {
            "t": item.get("t"),
            "speaker": item.get("speaker", ""),
            "text": text,
        }

        if any(k in text for k in decision_kw):
            decisions.append(entry)
        if any(k in text for k in task_kw):
            tasks.append(entry)
        if any(k in text for k in idea_kw):
            ideas.append(entry)
        if any(k in text for k in issue_kw):
            issues.append(entry)
        if "?" in text or any(k in text for k in question_kw):
            questions.append(entry)

    return {
        "decisions": decisions,
        "tasks": tasks,
        "ideas": ideas,
        "issues": issues,
        "questions": questions,
    }


def render_chat_transcript(tail: List[Dict[str, Any]]) -> None:
    if not tail:
        st.markdown("<span class='muted'>?? ??? ??</span>", unsafe_allow_html=True)
        return

    st.markdown("<div class='chat-wrap'>", unsafe_allow_html=True)
    for item in tail[-60:]:
        spk = html.escape(item.get("speaker", "Unknown") or "Unknown")
        text = html.escape((item.get("text") or "").strip())
        ts = html.escape(fmt_ts(item.get("t")))
        if not text:
            continue
        st.markdown(
            f"<div class='chat-row'>"
            f"<div class='chat-meta'>{spk} ? {ts}</div>"
            f"<div class='chat-bubble'>{text}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def render_live_analysis(live: Dict[str, Any]) -> None:
    drift = live.get("drift_score")
    status = live.get("drift_status")
    spark = live.get("spark_question")
    keywords = safe_list(live.get("top_keywords"))

    st.markdown("<div class='panel-title'>Topic Drift</div>", unsafe_allow_html=True)
    if drift is None:
        st.markdown("<span class='muted'>?? ?? ?</span>", unsafe_allow_html=True)
    else:
        label = "ON_TRACK" if status == "ON_TRACK" else "DRIFTING"
        badge_class = "badge-on" if status == "ON_TRACK" else "badge-off"
        st.markdown(f"<div class='metric'>{drift}</div>", unsafe_allow_html=True)
        st.markdown(
            f"<span class='badge {badge_class}'>{label}</span>",
            unsafe_allow_html=True,
        )

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title'>Keywords</div>", unsafe_allow_html=True)
    if keywords:
        for item in keywords[:12]:
            word = html.escape(str(item.get("word", "")))
            weight = item.get("weight", 0)
            st.markdown(f"<span class='kw-chip'>{word} {weight}</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span class='muted'>??? ??</span>", unsafe_allow_html=True)

    if spark:
        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
        st.markdown("<div class='panel-title'>Spark Question</div>", unsafe_allow_html=True)
        st.write(spark)


def render_comparison_table(table: Dict[str, Any]) -> None:
    if not table:
        st.markdown("<span class='muted'>?? ?? ??</span>", unsafe_allow_html=True)
        return
    for opt, data in table.items():
        st.markdown(f"**{opt}**")
        pros = safe_list(data.get("pros"))
        cons = safe_list(data.get("cons"))
        risks = safe_list(data.get("risks"))
        if pros:
            st.markdown("- Pros: " + ", ".join([str(x) for x in pros[:5]]))
        if cons:
            st.markdown("- Cons: " + ", ".join([str(x) for x in cons[:5]]))
        if risks:
            st.markdown("- Risks: " + ", ".join([str(x) for x in risks[:5]]))


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
left, right = st.columns([7, 4])

# Left column: summary + chat
with left:
    timeline = safe_list(data.get("progress_timeline"))
    tail = safe_list(data.get("recent_tail"))
    signals = extract_signals(tail)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title'>Transcript Summary</div>", unsafe_allow_html=True)
    st.write(latest_summary(timeline))
    if timeline:
        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
        for item in timeline[-4:]:
            st.write(f"[{fmt_ts(item.get('ts'))}] {item.get('text','')}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title'>Transcript</div>", unsafe_allow_html=True)
    render_chat_transcript(tail)
    st.markdown("</div>", unsafe_allow_html=True)

# Right column: agenda + live analysis + actions
with right:
    current_agenda = safe_dict(data.get("current_agenda"))
    pending_candidates = safe_list(data.get("pending_agenda_candidates"))
    live = safe_dict(data.get("live_analysis"))
    decision_log = safe_list(data.get("decision_log"))

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title'>Current Agenda</div>", unsafe_allow_html=True)
    if current_agenda:
        st.write(current_agenda.get("title", ""))
        st.markdown(f"<span class='muted'>??: {fmt_ts(current_agenda.get('started_at'))}</span>", unsafe_allow_html=True)
        if current_agenda.get("ended_at"):
            st.markdown(f"<br><span class='muted'>??: {fmt_ts(current_agenda.get('ended_at'))}</span>", unsafe_allow_html=True)
        if current_agenda.get("status"):
            st.markdown(f"<br><span class='muted'>??: {current_agenda.get('status')}</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span class='muted'>?? ??? ???? ?????.</span>", unsafe_allow_html=True)

    if pending_candidates and not current_agenda:
        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
        st.write("?? ??")
        cols = st.columns(3)
        for i in range(3):
            title = pending_candidates[i] if len(pending_candidates) > i else None
            with cols[i]:
                if title:
                    if st.button(title, key=f"agenda_btn_{i}", use_container_width=True):
                        try:
                            choose_agenda(title)
                            st.success(f"?? ???: {title}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"?? ?? ?? ??: {e}")
                else:
                    st.button("?", disabled=True, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title'>Live Analysis</div>", unsafe_allow_html=True)
    render_live_analysis(live)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title'>Decisions & Actions</div>", unsafe_allow_html=True)
    if decision_log:
        for d in decision_log[-5:]:
            spk = d.get("speaker", "")
            txt = d.get("text", "")
            st.markdown(f"- {spk}: {txt}")
    elif signals.get("tasks"):
        for item in signals["tasks"][-5:]:
            spk = item.get("speaker", "")
            txt = item.get("text", "")
            st.markdown(f"- {spk}: {txt}" if spk else f"- {txt}")
    else:
        st.markdown("<span class='muted'>?? ?? ??</span>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title'>Comparison Table</div>", unsafe_allow_html=True)
    render_comparison_table(live.get("comparison_table") if isinstance(live, dict) else {})
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='panel-title'>Risks & Questions</div>", unsafe_allow_html=True)
    if signals.get("issues") or signals.get("questions"):
        for item in signals.get("issues", [])[-3:]:
            st.markdown(f"- ???: {item.get('text','')}")
        for item in signals.get("questions", [])[-3:]:
            st.markdown(f"- ?? ??: {item.get('text','')}")
    else:
        st.markdown("<span class='muted'>???/?? ??</span>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.auto_refresh and not st.session_state.paused:
    time.sleep(st.session_state.refresh_sec)
    st.rerun()
