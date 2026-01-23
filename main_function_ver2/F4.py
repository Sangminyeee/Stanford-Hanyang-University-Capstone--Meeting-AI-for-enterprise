import os
import re
import json
import time
import asyncio
import datetime
from dataclasses import dataclass, field
from collections import deque, defaultdict
from typing import Deque, Dict, List, Optional, Tuple, Any

from google import genai
from google.genai import types


LINE_RE = re.compile(r"^\s*\[(?P<speaker>[^\]]+)\]\s*(?P<text>.+?)\s*$")
BRACKET_SPK_RE = re.compile(r"^\s*\[[^\]]+\]\s*")


def parse_transcript_line(line: str) -> Tuple[str, str]:
    m = LINE_RE.match(line or "")
    if not m:
        return "Unknown", (line or "").strip()
    return m.group("speaker").strip(), m.group("text").strip()


def strip_speaker_tag(line: str) -> str:
    return BRACKET_SPK_RE.sub("", (line or "")).strip()


def _ts_to_iso(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    try:
        return datetime.datetime.fromtimestamp(float(ts)).isoformat(timespec="seconds")
    except Exception:
        return None


def _now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(CURRENT_DIR, "../log")
REPORT_DIR = os.path.join(LOGS_DIR, "report")


@dataclass
class TranscriptLine:
    abs_idx: int
    ts: Optional[float]
    speaker: str
    text: str
    raw_line: str

    def ts_str(self) -> Optional[str]:
        return _ts_to_iso(self.ts)


class TranscriptStore:
    def __init__(self, max_full_lines: int = 20000, excerpt_lines: int = 400):
        self.max_full_lines = max_full_lines
        self.excerpt_lines = excerpt_lines
        self._lines: Deque[TranscriptLine] = deque(maxlen=max_full_lines)
        self._next_abs_idx = 0
        self._first_abs_idx = 0

    def add(self, ts: Optional[float], speaker: str, text: str, raw_line: str) -> TranscriptLine:
        abs_idx = self._next_abs_idx
        self._next_abs_idx += 1
        if len(self._lines) == self._lines.maxlen:
            self._first_abs_idx += 1
        line = TranscriptLine(abs_idx=abs_idx, ts=ts, speaker=speaker, text=text, raw_line=raw_line)
        self._lines.append(line)
        return line

    def full_text(self) -> str:
        return "\n".join([l.raw_line for l in self._lines])

    def excerpt_text(self) -> str:
        tail = list(self._lines)[-self.excerpt_lines :]
        return "\n".join([l.raw_line for l in tail])

    def tail_preview(self, n: int = 5) -> List[str]:
        return [l.raw_line for l in list(self._lines)[-n:]]

    def get_line_by_abs_idx(self, abs_idx: int) -> Optional[TranscriptLine]:
        if abs_idx < self._first_abs_idx:
            return None
        local = abs_idx - self._first_abs_idx
        if local < 0 or local >= len(self._lines):
            return None
        return list(self._lines)[local]

    def slice_by_abs_idx(self, start_abs: Optional[int], end_abs: Optional[int]) -> List[TranscriptLine]:
        if start_abs is None and end_abs is None:
            return list(self._lines)
        if start_abs is None:
            start_abs = self._first_abs_idx
        if end_abs is None:
            end_abs = self._next_abs_idx - 1
        if end_abs < start_abs:
            return []
        out = []
        for line in self._lines:
            if line.abs_idx < start_abs:
                continue
            if line.abs_idx > end_abs:
                break
            out.append(line)
        return out

    def evidence_snippet(self, abs_idx: int, max_lines: int = 3) -> List[str]:
        idxs = [abs_idx - 1, abs_idx, abs_idx + 1]
        out = []
        for i in idxs[:max_lines]:
            line = self.get_line_by_abs_idx(i)
            if not line:
                continue
            ts = line.ts_str()
            if ts:
                out.append(f"[{ts}] [{line.speaker}] {line.text}")
            else:
                out.append(f"[{line.speaker}] {line.text}")
        return out

    @property
    def next_abs_idx(self) -> int:
        return self._next_abs_idx

    @property
    def first_abs_idx(self) -> int:
        return self._first_abs_idx


class LLMClient:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.enabled = bool(self.api_key) and (genai is not None) and (types is not None)
        self._client = genai.Client(api_key=self.api_key) if self.enabled else None

    async def json_call(self, system: str, user: str, schema_hint: str) -> Optional[dict]:
        if not self.enabled:
            return None

        prompt = (
            f"{system}\n\n"
            f"[요청]\n{user}\n\n"
            f"[출력은 JSON ONLY]\n{schema_hint}\n"
        )

        def _call():
            resp = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            txt = (resp.text or "").strip()
            if txt.startswith("```json"):
                txt = txt[7:].strip()
            if txt.endswith("```"):
                txt = txt[:-3].strip()
            return json.loads(txt)

        try:
            return await asyncio.to_thread(_call)
        except Exception:
            return None


@dataclass
class AgendaSegment:
    agenda_id: str
    title: str
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    status: str = "in_progress"
    start_abs_idx: Optional[int] = None
    end_abs_idx: Optional[int] = None
    running_summary: str = ""


class Extractor:
    DECISION_KW = ["결정", "확정", "이걸로", "결론", "채택", "최종"]
    TASK_KW = ["할게", "하겠습니다", "담당", "까지", "해야", "진행", "액션"]
    IDEA_KW = ["아이디어", "대안", "제안", "옵션", "해보자"]
    ISSUE_KW = ["문제", "리스크", "우려", "막힘", "지연", "오류"]
    QUESTION_KW = ["질문", "궁금", "확인 필요"]

    DATE_PATTERNS = [
        re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
        re.compile(r"\b\d{1,2}/\d{1,2}\b"),
        re.compile(r"(오늘|내일|모레|이번주|다음주)"),
    ]

    def __init__(self, participants: Optional[List[str]] = None):
        self.participants = participants or []

    def _match_any(self, text: str, keywords: List[str]) -> bool:
        return any(k in text for k in keywords)

    def _infer_owner(self, text: str) -> Optional[str]:
        for p in self.participants:
            if p and p in text:
                return p
        return None

    def _infer_due(self, text: str) -> Optional[str]:
        for pat in self.DATE_PATTERNS:
            m = pat.search(text)
            if m:
                return m.group(0)
        return None

    def extract_from_lines(
        self,
        lines: List[TranscriptLine],
        store: TranscriptStore,
    ) -> Dict[str, Any]:
        decisions = []
        tasks = []
        ideas = []
        issues = []
        open_questions = []

        for line in lines:
            text = line.text
            if not text:
                continue

            if self._match_any(text, self.DECISION_KW):
                decisions.append({
                    "text": text,
                    "owner": self._infer_owner(text),
                    "evidence": store.evidence_snippet(line.abs_idx),
                })

            if self._match_any(text, self.TASK_KW):
                tasks.append({
                    "text": text,
                    "assignee": self._infer_owner(text),
                    "due": self._infer_due(text),
                    "status": "todo",
                    "evidence": store.evidence_snippet(line.abs_idx),
                })

            if self._match_any(text, self.IDEA_KW):
                ideas.append(text)

            if self._match_any(text, self.ISSUE_KW):
                issues.append(text)

            if "?" in text or self._match_any(text, self.QUESTION_KW):
                open_questions.append(text)

        return {
            "decisions": decisions,
            "tasks": tasks,
            "ideas": ideas,
            "issues": issues,
            "open_questions": open_questions,
        }


class MeetingFlowAI:
    def __init__(
        self,
        summary_interval_sec: int = 60,
        summary_window_sec: int = 180,
        live_min_interval_sec: int = 180,
        live_max_interval_sec: int = 300,
        topic_check_interval_sec: int = 20,
        propose_min_lines: int = 6,
        opinion_flush_interval_sec: int = 45,
        llm_model_name: str = None,
        window_max_lines: int = 200,
        max_full_lines: int = 20000,
        excerpt_lines: int = 400,
    ):
        self.summary_interval_sec = int(summary_interval_sec)
        self.summary_window_sec = int(summary_window_sec)
        self.live_min_interval_sec = int(live_min_interval_sec)
        self.live_max_interval_sec = int(live_max_interval_sec)
        self.topic_check_interval_sec = int(topic_check_interval_sec)
        self.propose_min_lines = int(propose_min_lines)
        self.opinion_flush_interval_sec = int(opinion_flush_interval_sec)
        self.window_max_lines = int(window_max_lines)

        self.llm = LLMClient(model_name=(llm_model_name or os.getenv("F4_GEMINI_MODEL") or "gemini-1.5-flash"))

        self._queue: asyncio.Queue[Tuple[Optional[float], str, str, str]] = asyncio.Queue()
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._pending_buffer: Deque[Tuple[Optional[float], str, str, str]] = deque(maxlen=2000)

        self._recent_lines: Deque[Tuple[float, str, str]] = deque(maxlen=self.window_max_lines)

        self.transcript = TranscriptStore(max_full_lines=max_full_lines, excerpt_lines=excerpt_lines)

        self.current_agenda: Optional[AgendaSegment] = None
        self.agenda_history: List[AgendaSegment] = []

        self._last_propose_at = 0.0
        self._last_topic_check_at = 0.0
        self._last_summary_at = 0.0
        self._last_opinion_flush_at = 0.0
        self._last_live_analysis_at = 0.0
        self._last_spark_at = 0.0

        self._awaiting_agenda_choice = False

        self.pending_agenda = {
            "candidates": [],
            "reason": "",
            "created_at": 0.0,
        }

        self.progress_summary = ""
        self.progress_timeline = deque(maxlen=50)

        self._decision_dedupe: Dict[str, float] = {}
        self.decision_context_lines = 2
        self.decision_dedupe_sec = 45
        self.decision_log: Deque[dict] = deque(maxlen=200)

        self.live_analysis = {
            "ts": None,
            "drift_score": None,
            "drift_status": None,
            "top_keywords": [],
            "comparison_table": {},
            "spark_question": None,
        }
        self.live_analysis_timeline: Deque[dict] = deque(maxlen=60)
        self._last_keywords_set = set()

        self.f1_basic_info: Dict[str, Any] = {}
        self.f2_meeting_summary: Optional[str] = None
        self.f3_agenda_info: Optional[dict] = None

    def update_basic_info(self, info: dict):
        if isinstance(info, dict):
            self.f1_basic_info = info

    def update_f2_summary(self, summary: str):
        if isinstance(summary, str):
            self.f2_meeting_summary = summary.strip()

    def update_f3_agenda_info(self, info: dict):
        if isinstance(info, dict):
            self.f3_agenda_info = info

    def _enqueue_line(self, payload: Tuple[Optional[float], str, str, str]):
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._queue.put_nowait, payload)
        else:
            self._pending_buffer.append(payload)

    def push_transcript_line(self, line: str, ts: Optional[str] = None, speaker: Optional[str] = None):
        raw_line = line or ""
        text = raw_line
        spk = speaker
        if speaker:
            raw_line = f"[{speaker}] {line}"
        if not speaker:
            spk, text = parse_transcript_line(raw_line)
        else:
            text = line

        ts_val: Optional[float] = None
        if ts:
            try:
                ts_val = float(ts)
            except Exception:
                ts_val = None
        if ts_val is None:
            ts_val = time.time()

        self._enqueue_line((ts_val, spk or "Unknown", text.strip(), raw_line.strip()))

    async def start(self):
        if self._running:
            return
        self._running = True
        self._loop = asyncio.get_running_loop()
        while self._pending_buffer:
            self._queue.put_nowait(self._pending_buffer.popleft())
        self._tasks = [
            asyncio.create_task(self._consumer_loop()),
            asyncio.create_task(self._periodic_loop()),
        ]
        print("\n[F4] MeetingFlowAI started.\n")

    async def stop(self):
        if not self._running:
            return
        self._running = False
        if self.current_agenda and self.current_agenda.ended_at is None:
            self.current_agenda.ended_at = time.time()
            self.current_agenda.status = "completed"
            self.current_agenda.end_abs_idx = self.transcript.next_abs_idx - 1
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        try:
            report_path = await self.save_post_meeting_report()
            if report_path:
                print(f"\n[F4] Post-meeting report saved: {report_path}\n")
        except Exception as e:
            print(f"[F4] Report save error: {e}")
        print("\n[F4] MeetingFlowAI stopped.\n")

    async def _consumer_loop(self):
        while self._running:
            try:
                ts, speaker, text, raw_line = await self._queue.get()
                if not text:
                    continue
                line = self.transcript.add(ts, speaker, text, raw_line)
                self._recent_lines.append((ts, speaker, text))

                self._maybe_capture_decision(line)

                if self.current_agenda:
                    self.current_agenda.end_abs_idx = line.abs_idx

                if (self.current_agenda is None) and (len(self._recent_lines) >= self.propose_min_lines):
                    await self._propose_and_choose_agenda(reason="초기 안건 설정")

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[F4] consumer error: {e}")
            finally:
                try:
                    self._queue.task_done()
                except Exception:
                    pass

    async def _periodic_loop(self):
        self._last_summary_at = time.time()
        self._last_topic_check_at = time.time()
        self._last_opinion_flush_at = time.time()
        self._last_live_analysis_at = time.time()

        while self._running:
            try:
                await asyncio.sleep(0.5)
                now = time.time()

                if self.current_agenda and (now - self._last_summary_at >= self.summary_interval_sec):
                    await self._emit_progress_summary()
                    self._last_summary_at = now

                if self.current_agenda and (now - self._last_topic_check_at >= self.topic_check_interval_sec):
                    await self._check_topic_shift()
                    self._last_topic_check_at = now

                if (now - self._last_live_analysis_at) >= self._adaptive_live_interval():
                    await self._run_live_analysis()
                    self._last_live_analysis_at = now

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[F4] periodic error: {e}")

    def _window_text(self, seconds: Optional[int] = None, strip_speaker: bool = False) -> str:
        if not self._recent_lines:
            return ""
        now = time.time()
        items = list(self._recent_lines)
        if seconds is not None:
            items = [x for x in items if (now - x[0]) <= seconds]
        tail = items[-120:]
        if strip_speaker:
            return "\n".join([strip_speaker_tag(txt) for _, _, txt in tail if txt.strip()])
        return "\n".join([f"[{spk}] {txt}" for _, spk, txt in tail])

    def _adaptive_live_interval(self) -> int:
        now = time.time()
        recent = [x for x in self._recent_lines if (now - x[0]) <= 60]
        if len(recent) >= 6:
            return self.live_min_interval_sec
        return self.live_max_interval_sec

    def _keyword_weights(self, text: str, limit: int = 12) -> List[Dict[str, Any]]:
        tokens = re.findall(r"[가-힣A-Za-z0-9]{2,}", text or "")
        if not tokens:
            return []
        stop = {
            "그리고", "그래서", "그런데", "저희", "우리", "여기", "거기", "이번",
            "이것", "그것", "저것", "그냥", "사실", "말씀", "부분", "정도", "때문",
            "회의", "안건", "관련", "검토", "논의",
        }
        freq: Dict[str, int] = {}
        for t in tokens:
            if t in stop:
                continue
            freq[t] = freq.get(t, 0) + 1
        if not freq:
            return []
        top = sorted(freq.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))[:limit]
        max_f = max(1, top[0][1])
        out = []
        for word, f in top:
            weight = int(round((f / max_f) * 100))
            out.append({"word": word, "weight": weight})
        return out

    def _agenda_text(self) -> str:
        if self.current_agenda and self.current_agenda.title:
            return self.current_agenda.title
        if isinstance(self.f3_agenda_info, dict):
            parts = []
            for v in self.f3_agenda_info.values():
                if isinstance(v, str):
                    parts.append(v)
                elif isinstance(v, list):
                    parts.extend([str(x) for x in v if isinstance(x, str)])
            return " ".join(parts).strip()
        return ""

    def _topic_drift(self, dialog_text: str) -> Tuple[Optional[int], Optional[str]]:
        agenda = self._agenda_text()
        if not agenda or not dialog_text:
            return None, None

        def _tok(s: str) -> set:
            return set(re.findall(r"[가-힣A-Za-z0-9]{2,}", s or ""))

        a = _tok(agenda)
        d = _tok(dialog_text)
        if not a or not d:
            return None, None
        inter = len(a & d)
        union = len(a | d)
        sim = inter / max(1, union)
        drift_score = int(round(sim * 100))
        status = "ON_TRACK" if drift_score >= 60 else "DRIFTING"
        return drift_score, status

    async def _llm_comparison_table(self, window_text: str) -> Dict[str, Any]:
        if not self.llm or not getattr(self.llm, "enabled", False):
            return {}
        system = "너는 회의 비교 분석 도우미다. 선택지 간 비교를 구조화한다."
        user = (
            "아래 전사에서 비교 논의(예: A vs B, 대안 비교, 장단점)를 찾아라.\n"
            "비교가 없다면 빈 객체를 반환한다.\n\n"
            f"[전사]\n{window_text}\n"
        )
        schema = '{"comparison_table": {"Option A": {"pros": [], "cons": [], "risks": []}}}'
        out = await self.llm.json_call(system, user, schema)
        if not out:
            return {}
        table = out.get("comparison_table") if isinstance(out, dict) else None
        return table if isinstance(table, dict) else {}

    async def _llm_spark_question(self, window_text: str) -> Optional[str]:
        if not self.llm or not getattr(self.llm, "enabled", False):
            return None
        agenda = self._agenda_text() or "현재 안건"
        system = "너는 회의 촉진자다. 막힌 대화를 확장하는 질문을 한 문장으로 제시한다."
        user = (
            f"현재 안건: {agenda}\n\n"
            f"최근 전사:\n{window_text}\n\n"
            "요구: 기존 발화와 다른 관점을 여는 질문 1문장."
        )
        schema = '{"spark_question": "질문 한 문장"}'
        out = await self.llm.json_call(system, user, schema)
        if not out:
            return None
        q = (out.get("spark_question") or "").strip()
        return q or None

    def _should_spark(self, window_text: str, keywords: List[Dict[str, Any]]) -> bool:
        if not window_text.strip():
            return False
        if time.time() - self._last_spark_at < 180:
            return False
        idea_kw = ("아이디어", "대안", "제안", "옵션", "해보자")
        detail_kw = ("구체", "디테일", "세부", "방법", "방안")
        if any(k in window_text for k in idea_kw):
            return False
        if any(k in window_text for k in detail_kw):
            return False

        kw_set = {k["word"] for k in keywords if k.get("word")}
        if not kw_set:
            return True
        overlap = len(kw_set & self._last_keywords_set) / max(1, len(kw_set | self._last_keywords_set))
        self._last_keywords_set = kw_set
        if overlap >= 0.8 and len(kw_set) <= 6:
            return True
        return False

    async def _run_live_analysis(self):
        window_text = self._window_text(seconds=self.summary_window_sec, strip_speaker=True)
        drift_score, drift_status = self._topic_drift(window_text)
        keywords = self._keyword_weights(window_text, limit=12)
        comparison_table = await self._llm_comparison_table(window_text)

        spark_question = None
        if self._should_spark(window_text, keywords):
            spark_question = await self._llm_spark_question(window_text)
            if not spark_question:
                spark_question = "만약 제약이 없다고 가정하면, 어떤 접근이 가능할까요?"
            self._last_spark_at = time.time()

        now_iso = _now_iso()
        self.live_analysis = {
            "ts": now_iso,
            "drift_score": drift_score,
            "drift_status": drift_status,
            "top_keywords": keywords,
            "comparison_table": comparison_table,
            "spark_question": spark_question,
        }
        self.live_analysis_timeline.append(self.live_analysis)

    async def _emit_progress_summary(self):
        w = self._window_text(seconds=self.summary_window_sec, strip_speaker=True)
        if not w.strip():
            return
        system = "너는 실시간 회의 서기다. 과장 없이, 현재 진행 상태를 한 문장으로 보고한다."
        user = (
            f"최근 전사:\n{w}\n\n"
            "요구:\n"
            "- 한국어 한 문장\n"
            "- 반드시 '...하는 중입니다' 형태\n"
            "- 안건을 명시\n"
        )
        schema = '{"progress": "현재 ~~ 안건에 대해 ~~하는 중입니다."}'

        out = None
        if self.llm and getattr(self.llm, "enabled", False):
            out = await self.llm.json_call(system=system, user=user, schema_hint='{"progress":"..."}')

        progress = ""
        if isinstance(out, dict):
            progress = (out.get("progress") or "").strip()
        if not progress:
            progress = "현재 회의 내용을 정리하는 중입니다."

        self.progress_summary = progress
        self.progress_timeline.append((time.time(), progress))

    async def _propose_and_choose_agenda(self, reason: str):
        if self._awaiting_agenda_choice:
            return
        now = time.time()
        if now - self._last_propose_at < 15:
            return
        self._last_propose_at = now

        w = self._window_text(seconds=180, strip_speaker=True)
        if not w.strip():
            return

        candidates = await self._propose_agenda_candidates(w)
        if not candidates:
            candidates = self._fallback_candidates(w)

        self.pending_agenda = {
            "candidates": candidates[:3],
            "reason": reason,
            "created_at": time.time(),
        }

    async def propose_agenda_now(self, reason: str = "manual"):
        await self._propose_and_choose_agenda(reason=reason)

    async def choose_agenda(self, title: str):
        title = (title or "").strip()
        if not title:
            return
        self.pending_agenda = {"candidates": [], "reason": "", "created_at": 0.0}
        await self._switch_agenda(title, reason="UI 선택")

    async def _propose_agenda_candidates(self, window_text: str) -> List[str]:
        system = "너는 회의 안건 정리 전문가다. 전사 내용을 바탕으로 중복 없는 안건 제목 후보를 만든다."
        user = (
            "아래 전사를 읽고, 현재 논의 중인 안건 후보 3개를 짧은 제목으로 제시해라.\n"
            "조건:\n"
            "- 후보는 서로 달라야 함\n"
            "- 각 후보는 4~12자 내외(가능하면)\n"
            "- 너무 포괄적인 단어만(예: '회의') 금지\n\n"
            f"[전사]\n{window_text}\n"
        )
        schema = '{"candidates": ["후보1", "후보2", "후보3"]}'
        out = await self.llm.json_call(system, user, schema)
        if not out or "candidates" not in out:
            return []
        cands = out.get("candidates")
        if not isinstance(cands, list):
            return []
        cleaned = []
        for x in cands:
            s = str(x).strip()
            if s and s not in cleaned:
                cleaned.append(s)
        return cleaned[:3]

    def _fallback_candidates(self, window_text: str) -> List[str]:
        candidates = []
        lines = [l.strip() for l in window_text.splitlines() if l.strip()]
        agenda_markers = ["안건", "주제", "논의", "이슈", "목표", "agenda", "topic", "issue"]

        def _clean_title(s: str) -> str:
            s = re.sub(r"^\s*[\-\*\d\.\)]\s*", "", s)
            s = re.sub(r"^\s*(안건|주제|논의|이슈|목표)\s*[:\-]?\s*", "", s, flags=re.IGNORECASE)
            s = re.sub(r"\s+", " ", s).strip()
            if len(s) > 40:
                s = s[:40].rstrip()
            return s

        for line in lines:
            if any(m in line for m in agenda_markers):
                title = _clean_title(line)
                if 4 <= len(title) <= 40 and title not in candidates:
                    candidates.append(title)

        for line in lines:
            m = re.search(r"(.{2,30}?)(?:에 대해|관련|진행|검토|논의)", line)
            if m:
                title = _clean_title(m.group(1))
                if 4 <= len(title) <= 40 and title not in candidates:
                    candidates.append(title)

        if len(candidates) < 3:
            words = re.findall(r"[가-힣A-Za-z0-9]{2,}", window_text)
            freq = defaultdict(int)
            for w in words:
                freq[w] += 1
            top = sorted(freq.items(), key=lambda kv: (-kv[1], -len(kv[0])))[:8]
            base = [w for w, _ in top if len(w) >= 2]
            for w in base:
                if w not in candidates and len(candidates) < 6:
                    candidates.append(w)

        if not candidates:
            return ["진행사항", "이슈정리", "다음액션"]
        return candidates[:3]

    async def _switch_agenda(self, title: str, reason: str):
        title = (title or "").strip()
        if not title:
            return
        if self.current_agenda and self.current_agenda.title == title:
            return

        if self.current_agenda:
            self.current_agenda.ended_at = time.time()
            self.current_agenda.status = "completed"
            self.current_agenda.end_abs_idx = self.transcript.next_abs_idx - 1
            self.agenda_history.append(self.current_agenda)

        agenda_id = f"agenda-{len(self.agenda_history) + 1}"
        self.current_agenda = AgendaSegment(
            agenda_id=agenda_id,
            title=title,
            started_at=time.time(),
            ended_at=None,
            status="in_progress",
            start_abs_idx=self.transcript.next_abs_idx,
            end_abs_idx=None,
        )

    async def _check_topic_shift(self):
        w = self._window_text(seconds=120, strip_speaker=True)
        if not w.strip() or not self.current_agenda:
            return
        shift_signals = ("다음", "그럼", "넘어가", "전환", "또", "추가로", "마지막으로", "다른 건")
        if any(sig in w for sig in shift_signals):
            ok = await self._llm_is_same_agenda(self.current_agenda.title, w)
            if ok is False:
                await self._propose_and_choose_agenda(reason="안건 변경 감지")

    async def _llm_is_same_agenda(self, agenda_title: str, window_text: str) -> Optional[bool]:
        system = "너는 회의 흐름 감지기다. 현재 전사가 기존 안건에 부합하는지 판정한다."
        user = (
            f"현재 안건: {agenda_title}\n\n"
            f"최근 전사:\n{window_text}\n\n"
            "질문: 최근 전사가 '현재 안건'을 계속 논의하는 흐름이면 true, 아니면 false.\n"
            "- 보수적으로 판단(바뀐 게 확실할 때만 false)\n"
        )
        schema = '{"same": true}'
        out = await self.llm.json_call(system, user, schema)
        if not out or "same" not in out:
            return None
        return bool(out["same"])

    def _agenda_list(self) -> List[AgendaSegment]:
        ags = list(self.agenda_history)
        if self.current_agenda:
            ags.append(self.current_agenda)
        return ags

    def _agenda_summary_from_lines(self, lines: List[TranscriptLine], max_sent: int = 2) -> str:
        if not lines:
            return ""
        texts = [l.text for l in lines if l.text]
        if not texts:
            return ""
        return " ".join(texts[:max_sent])

    def _norm_for_dedupe(self, s: str) -> str:
        s = (s or "").strip().lower()
        s = re.sub(r"\s+", " ", s)
        s = re.sub(r"[\"'`]", "", s)
        return s[:200]

    def _maybe_capture_decision(self, line: TranscriptLine):
        text = (line.text or "").strip()
        if len(text) < 4:
            return
        kw = Extractor.DECISION_KW
        if not any(k in text for k in kw):
            return

        ts_val = line.ts if line.ts is not None else time.time()
        key = self._norm_for_dedupe(text)
        last = self._decision_dedupe.get(key, 0.0)
        if ts_val - last < self.decision_dedupe_sec:
            return
        self._decision_dedupe[key] = ts_val

        agenda_title = self.current_agenda.title if self.current_agenda else "Unassigned"
        evidence = self.transcript.evidence_snippet(line.abs_idx, max_lines=self.decision_context_lines)
        self.decision_log.append({
            "t": ts_val,
            "speaker": line.speaker,
            "text": text,
            "agenda": agenda_title,
            "confidence": 0.6,
            "evidence": evidence,
        })

    def _extract_recent_signals(self, max_lines: int = 60) -> Dict[str, Any]:
        start = max(self.transcript.first_abs_idx, self.transcript.next_abs_idx - max_lines)
        lines = self.transcript.slice_by_abs_idx(start, self.transcript.next_abs_idx - 1)
        participants = self.f1_basic_info.get("participants") if isinstance(self.f1_basic_info, dict) else []
        extractor = Extractor(participants=participants)
        return extractor.extract_from_lines(lines, self.transcript)

    def _signals_for_ui(self, lines: List[TranscriptLine]) -> Dict[str, List[Dict[str, Any]]]:
        decision_kw = ("결정", "확정", "이걸로", "결론", "채택", "최종", "합의", "정하자")
        task_kw = ("할게", "하겠습니다", "담당", "까지", "해야", "진행", "액션", "요청")
        idea_kw = ("아이디어", "대안", "제안", "옵션", "해보자")
        issue_kw = ("문제", "리스크", "우려", "막힘", "지연", "오류")
        question_kw = ("질문", "궁금", "확인 필요")

        decisions = []
        tasks = []
        ideas = []
        issues = []
        questions = []

        for line in lines:
            text = (line.text or "").strip()
            if not text:
                continue
            entry = {
                "t": line.ts_str(),
                "speaker": line.speaker or "Unknown",
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

    def _build_flow_timeline(self) -> List[dict]:
        if self.progress_timeline:
            return [{"ts": _ts_to_iso(ts), "text": txt} for ts, txt in list(self.progress_timeline)]
        items = []
        lines = list(self.transcript._lines)
        if not lines:
            return items
        step = max(1, len(lines) // 5)
        for i in range(0, len(lines), step):
            line = lines[i]
            items.append({"ts": line.ts_str(), "text": line.text})
        return items

    def _validate_minutes(self, data: dict) -> bool:
        try:
            if not isinstance(data, dict):
                return False
            required = [
                "basic_info",
                "inputs",
                "meeting_text",
                "flow_summary",
                "agenda_items",
                "tasks_by_person",
                "unassigned_tasks",
                "risks",
                "open_questions",
                "meta",
            ]
            for k in required:
                if k not in data:
                    return False
            if not isinstance(data["agenda_items"], list):
                return False
            if not isinstance(data["tasks_by_person"], dict):
                return False
            if not isinstance(data["unassigned_tasks"], list):
                return False
            if not isinstance(data["risks"], list):
                return False
            if not isinstance(data["open_questions"], list):
                return False
            return True
        except Exception:
            return False

    async def _llm_refine_minutes(self, base: dict) -> Tuple[Optional[dict], Optional[str]]:
        if not self.llm or not getattr(self.llm, "enabled", False):
            return None, "llm_disabled"
        system = "너는 회의 서기다. 입력 JSON을 개선해 동일한 스키마로 출력한다."
        user = (
            "아래 JSON을 기준으로 회의록을 다듬어라. "
            "스키마는 유지하고 내용만 개선한다.\n"
            f"{json.dumps(base, ensure_ascii=False)}"
        )
        schema = json.dumps(self._minutes_schema(), ensure_ascii=False)
        out = await self.llm.json_call(system, user, schema)
        if not out:
            return None, "llm_no_output"
        if not self._validate_minutes(out):
            return None, "llm_invalid_schema"
        return out, None

    def _minutes_schema(self) -> dict:
        return {
            "basic_info": {"title": None, "date": None, "participants": [], "location": None},
            "inputs": {"f2_summary": None, "f3_agenda_info": None},
            "meeting_text": {"full": "", "excerpt": ""},
            "flow_summary": {"high_level": "", "timeline": [{"ts": None, "text": ""}]},
            "agenda_items": [
                {
                    "agenda_id": "",
                    "title": "",
                    "started_at": None,
                    "ended_at": None,
                    "status": "in_progress",
                    "summary": "",
                    "ideas": [],
                    "decisions": [{"text": "", "owner": None, "evidence": []}],
                    "tasks": [{"text": "", "assignee": None, "due": None, "status": "todo", "evidence": []}],
                    "issues": [],
                    "open_questions": [],
                }
            ],
            "tasks_by_person": {},
            "unassigned_tasks": [],
            "risks": [],
            "open_questions": [],
            "meta": {"generated_at": "", "llm_used": False, "fallback_reason": None},
        }

    async def create_meeting_minutes(self) -> dict:
        participants = self.f1_basic_info.get("participants") if isinstance(self.f1_basic_info, dict) else []
        extractor = Extractor(participants=participants)

        agenda_items = []
        all_tasks = []
        all_open_questions = []
        all_risks = []

        for ag in self._agenda_list():
            lines = self.transcript.slice_by_abs_idx(ag.start_abs_idx, ag.end_abs_idx)
            extracted = extractor.extract_from_lines(lines, self.transcript)
            summary = ag.running_summary or self._agenda_summary_from_lines(lines)
            item = {
                "agenda_id": ag.agenda_id,
                "title": ag.title,
                "started_at": _ts_to_iso(ag.started_at),
                "ended_at": _ts_to_iso(ag.ended_at),
                "status": ag.status,
                "summary": summary,
                "ideas": extracted["ideas"],
                "decisions": extracted["decisions"],
                "tasks": extracted["tasks"],
                "issues": extracted["issues"],
                "open_questions": extracted["open_questions"],
            }
            agenda_items.append(item)
            all_tasks.extend(item["tasks"])
            all_open_questions.extend(item["open_questions"])
            all_risks.extend(item["issues"])

        tasks_by_person: Dict[str, List[dict]] = defaultdict(list)
        unassigned_tasks = []
        for t in all_tasks:
            entry = {
                "text": t.get("text", ""),
                "due": t.get("due"),
                "status": t.get("status", "todo"),
                "agenda_id": None,
            }
            if t.get("assignee"):
                tasks_by_person[t["assignee"]].append(entry)
            else:
                unassigned_tasks.append(entry)

        high_level = self.progress_summary or "회의 내용을 요약 중입니다."
        flow = {
            "high_level": high_level,
            "timeline": self._build_flow_timeline(),
        }

        base = {
            "basic_info": {
                "title": self.f1_basic_info.get("title") if isinstance(self.f1_basic_info, dict) else None,
                "date": self.f1_basic_info.get("date") if isinstance(self.f1_basic_info, dict) else None,
                "participants": participants or [],
                "location": self.f1_basic_info.get("location") if isinstance(self.f1_basic_info, dict) else None,
            },
            "inputs": {
                "f2_summary": self.f2_meeting_summary,
                "f3_agenda_info": self.f3_agenda_info,
            },
            "meeting_text": {
                "full": self.transcript.full_text(),
                "excerpt": self.transcript.excerpt_text(),
            },
            "flow_summary": flow,
            "agenda_items": agenda_items,
            "tasks_by_person": dict(tasks_by_person),
            "unassigned_tasks": unassigned_tasks,
            "risks": list(dict.fromkeys(all_risks))[:50],
            "open_questions": list(dict.fromkeys(all_open_questions))[:50],
            "meta": {
                "generated_at": _now_iso(),
                "llm_used": False,
                "fallback_reason": None,
            },
        }

        llm_out, reason = await self._llm_refine_minutes(base)
        if llm_out and self._validate_minutes(llm_out):
            llm_out["meta"]["generated_at"] = _now_iso()
            llm_out["meta"]["llm_used"] = True
            llm_out["meta"]["fallback_reason"] = None
            return llm_out

        base["meta"]["llm_used"] = False
        base["meta"]["fallback_reason"] = reason
        if not self._validate_minutes(base):
            base = self._minutes_schema()
            base["meta"]["generated_at"] = _now_iso()
            base["meta"]["llm_used"] = False
        base["meta"]["fallback_reason"] = "schema_repair"
        return base

    def _alignment_fallback(self, agenda_items: List[dict]) -> List[dict]:
        report = []
        for item in agenda_items:
            decisions = item.get("decisions") or []
            issues = item.get("issues") or []
            open_q = item.get("open_questions") or []
            status = "DEFERRED"
            if decisions:
                status = "AGREED"
            elif issues or open_q:
                status = "CONFLICT"
            report.append({
                "agenda_id": item.get("agenda_id"),
                "title": item.get("title"),
                "status": status,
                "reason": "heuristic",
            })
        return report

    def _action_items_fallback(self, agenda_items: List[dict]) -> List[dict]:
        out = []
        for item in agenda_items:
            tasks = item.get("tasks") or []
            for t in tasks:
                evidence = t.get("evidence") or []
                context = evidence[0] if evidence else None
                out.append({
                    "task": t.get("text") or "",
                    "assignee": t.get("assignee"),
                    "due_date": t.get("due"),
                    "context_link": context,
                })
        return out

    def _layered_summary_fallback(self, agenda_items: List[dict]) -> Dict[str, Any]:
        lines = []
        for item in agenda_items[:3]:
            title = item.get("title") or "안건"
            summary = item.get("summary") or ""
            line = f"{title}: {summary}".strip()
            if line:
                lines.append(line)
        while len(lines) < 3:
            lines.append("회의 요약 생성 대기 중입니다.")
        discussion_flow = " ".join([item.get("summary") or "" for item in agenda_items if item.get("summary")]).strip()
        if not discussion_flow:
            discussion_flow = self.progress_summary or "회의 진행을 정리하는 중입니다."
        return {
            "executive_summary": lines[:3],
            "discussion_flow": discussion_flow,
        }

    def _insight_metrics_fallback(self) -> Dict[str, Any]:
        speaker_counts: Dict[str, int] = defaultdict(int)
        for line in list(self.transcript._lines):
            speaker_counts[line.speaker or "Unknown"] += 1
        if speaker_counts:
            dominant = max(speaker_counts.items(), key=lambda kv: kv[1])[0]
        else:
            dominant = None
        return {
            "speaker_distribution": dict(speaker_counts),
            "dominant_speaker": dominant,
            "agenda_count": len(self._agenda_list()),
            "decision_count": len(self.decision_log),
        }

    async def _llm_post_meeting(self, base: dict) -> Optional[dict]:
        if not self.llm or not getattr(self.llm, "enabled", False):
            return None
        system = "너는 회의 문서화 전문가다. 입력 JSON을 분석해 회의 종료 문서를 생성한다."
        user = (
            "아래 JSON을 참고해 정리된 보고서를 만들어라. "
            "스키마를 반드시 지켜라.\n"
            f"{json.dumps(base, ensure_ascii=False)}"
        )
        schema = json.dumps({
            "alignment_report": [{"agenda_id": "", "title": "", "status": "AGREED|CONFLICT|DEFERRED", "reason": ""}],
            "action_items": [{"task": "", "assignee": None, "due_date": None, "context_link": None}],
            "layered_summary": {"executive_summary": ["", "", ""], "discussion_flow": ""},
            "insight_metrics": {},
        }, ensure_ascii=False)
        out = await self.llm.json_call(system, user, schema)
        if not isinstance(out, dict):
            return None
        return out

    async def create_post_meeting_report(self) -> dict:
        minutes = await self.create_meeting_minutes()
        agenda_items = minutes.get("agenda_items") or []

        base = {
            "alignment_report": self._alignment_fallback(agenda_items),
            "action_items": self._action_items_fallback(agenda_items),
            "layered_summary": self._layered_summary_fallback(agenda_items),
            "insight_metrics": self._insight_metrics_fallback(),
        }

        llm_out = await self._llm_post_meeting({
            "agenda_items": agenda_items,
            "meeting_text_excerpt": minutes.get("meeting_text", {}).get("excerpt", ""),
            "signals": minutes.get("open_questions", []),
            "decisions": minutes.get("agenda_items", []),
        })
        if llm_out:
            for key in ["alignment_report", "action_items", "layered_summary", "insight_metrics"]:
                if key in llm_out:
                    base[key] = llm_out[key]

        return {
            "generated_at": _now_iso(),
            "alignment_report": base["alignment_report"],
            "action_items": base["action_items"],
            "layered_summary": base["layered_summary"],
            "insight_metrics": base["insight_metrics"],
        }

    async def save_post_meeting_report(self) -> Optional[str]:
        os.makedirs(REPORT_DIR, exist_ok=True)
        report = await self.create_post_meeting_report()
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(REPORT_DIR, f"report_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        return path

    def get_state(self) -> dict:
        current_agenda = None
        if self.current_agenda:
            current_agenda = {
                "agenda_id": self.current_agenda.agenda_id,
                "title": self.current_agenda.title,
                "started_at": _ts_to_iso(self.current_agenda.started_at),
                "ended_at": _ts_to_iso(self.current_agenda.ended_at),
                "status": self.current_agenda.status,
            }
        recent_lines = []
        for line in self.transcript.slice_by_abs_idx(
            max(self.transcript.first_abs_idx, self.transcript.next_abs_idx - 30),
            self.transcript.next_abs_idx - 1,
        ):
            recent_lines.append({
                "t": line.ts_str(),
                "speaker": line.speaker,
                "text": line.text,
            })

        agenda_history = []
        for ag in self.agenda_history[-10:]:
            agenda_history.append({
                "agenda_id": ag.agenda_id,
                "title": ag.title,
                "started_at": _ts_to_iso(ag.started_at),
                "ended_at": _ts_to_iso(ag.ended_at),
                "status": ag.status,
                "summary": ag.running_summary,
            })

        recent_signal_lines = self.transcript.slice_by_abs_idx(
            max(self.transcript.first_abs_idx, self.transcript.next_abs_idx - 60),
            self.transcript.next_abs_idx - 1,
        )
        signals_ui = self._signals_for_ui(recent_signal_lines)
        signals_detail = self._extract_recent_signals()

        return {
            "ts": _now_iso(),
            "current_agenda": current_agenda,
            "pending_agenda_candidates": list(self.pending_agenda.get("candidates", [])),
            "progress_timeline": [{"ts": _ts_to_iso(ts), "text": txt} for ts, txt in list(self.progress_timeline)],
            "meeting_text_tail_preview": self.transcript.tail_preview(5),
            "recent_tail": recent_lines,
            "decision_log": list(self.decision_log)[-20:],
            "agenda_history": agenda_history,
            "signals": signals_ui,
            "signals_detail": signals_detail,
            "live_analysis": dict(self.live_analysis),
            "live_analysis_timeline": list(self.live_analysis_timeline),
            "candidate_counts": {
                "agenda_history": len(self.agenda_history),
                "pending_candidates": len(self.pending_agenda.get("candidates", [])),
            },
        }


def _test_basic():
    async def _run():
        f4 = MeetingFlowAI()
        f4.update_basic_info({"title": "Weekly Sync", "date": "2026-01-23", "participants": ["Alice", "Bob"], "location": "Room A"})
        await f4.start()
        f4.push_transcript_line("[Alice] 이번주 목표 정리하죠")
        f4.push_transcript_line("[Bob] 이건 결정 사항으로 합시다")
        f4.push_transcript_line("[Alice] 제가 담당할게요 다음주까지")
        await asyncio.sleep(0.1)
        await f4.choose_agenda("주간 목표")
        await asyncio.sleep(0.1)
        minutes = await f4.create_meeting_minutes()
        assert isinstance(minutes, dict)
        for key in ["basic_info", "inputs", "meeting_text", "flow_summary", "agenda_items", "tasks_by_person", "unassigned_tasks", "risks", "open_questions", "meta"]:
            assert key in minutes
        await f4.stop()

    asyncio.run(_run())


if __name__ == "__main__":
    _test_basic()
