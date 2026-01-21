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

# 내용 요약할때 최근 내용만 요약하게 기존 전사 내용 요약
LINE_RE = re.compile(r"^\s*\[(?P<speaker>[^\]]+)\]\s*(?P<text>.+?)\s*$")


def parse_transcript_line(line: str) -> Tuple[str, str]:
    m = LINE_RE.match(line or "")
    if not m:
        return "Unknown", (line or "").strip()
    return m.group("speaker").strip(), m.group("text").strip()


def now_hhmm() -> str:
    return datetime.datetime.now().strftime("%H:%M")


# -----------------------------
# LLM 클라이언트 (Gemini + fallback)
# -----------------------------
class LLMClient:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.enabled = bool(self.api_key) and (genai is not None) and (types is not None)
        self._client = genai.Client(api_key=self.api_key) if self.enabled else None

    async def json_call(self, system: str, user: str, schema_hint: str) -> Optional[dict]:
        """
        JSON만 받는 호출. 실패하면 None.
        """
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
                )
            )
            txt = (resp.text or "").strip()
            # 방어적 클리닝
            if txt.startswith("```json"):
                txt = txt[7:].strip()
            if txt.endswith("```"):
                txt = txt[:-3].strip()
            return json.loads(txt)

        try:
            return await asyncio.to_thread(_call)
        except Exception:
            return None


# -----------------------------
# 데이터 모델
# -----------------------------
@dataclass
class AgendaItem:
    title: str
    started_at: float = field(default_factory=lambda: time.time())
    # 누적 요약 / 의견
    running_summary: str = ""
    opinions_by_speaker: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    decisions: List[str] = field(default_factory=list)
    todos: List[str] = field(default_factory=list)


# -----------------------------
# 핵심: 실시간 회의 흐름 AI
# -----------------------------
class MeetingFlowAI:
    def __init__(
            self,
            summary_interval_sec: int = 60,
            topic_check_interval_sec: int = 20,
            propose_min_lines: int = 6,
            opinion_flush_interval_sec: int = 45,
            llm_model_name: str = None,
            window_max_lines: int = 200,
    ):
        self.summary_interval_sec = int(summary_interval_sec)
        self.topic_check_interval_sec = int(topic_check_interval_sec)
        self.propose_min_lines = int(propose_min_lines)
        self.opinion_flush_interval_sec = int(opinion_flush_interval_sec)
        self.window_max_lines = int(window_max_lines)

        self.llm = LLMClient(model_name=(llm_model_name or os.getenv("F4_GEMINI_MODEL") or "gemini-1.5-flash"))

        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._running = False
        self._tasks: List[asyncio.Task] = []

        # 최근 전사 윈도우
        self._recent_lines: Deque[Tuple[float, str, str]] = deque(maxlen=self.window_max_lines)
        # (ts, speaker, text)

        # 안건/상태
        self.current_agenda: Optional[AgendaItem] = None
        self.agenda_history: List[AgendaItem] = []

        # 안건 후보 제시 쿨다운
        self._last_propose_at = 0.0
        self._last_topic_check_at = 0.0
        self._last_summary_at = 0.0
        self._last_opinion_flush_at = 0.0

        # 안건 선택/변경 중복 방지
        self._awaiting_agenda_choice = False

    # 외부(연결파일)에서 호출
    def push_transcript_line(self, line: str):
        # queue.put_nowait는 event loop에서만 안전 -> 연결파일에서 call_soon_threadsafe로 호출하도록 설계함
        self._queue.put_nowait(line)

    async def start(self):
        if self._running:
            return
        self._running = True
        self._tasks = [
            asyncio.create_task(self._consumer_loop()),
            asyncio.create_task(self._periodic_loop()),
        ]
        print("\n[F4] MeetingFlowAI started.\n")

    async def stop(self):
        if not self._running:
            return
        self._running = False
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        print("\n[F4] MeetingFlowAI stopped.\n")

    # -----------------------------
    # 메인: 전사 라인 소비
    # -----------------------------
    async def _consumer_loop(self):
        while self._running:
            try:
                line = await self._queue.get()
                ts = time.time()
                speaker, text = parse_transcript_line(line)

                if not text:
                    continue

                self._recent_lines.append((ts, speaker, text))

                # 안건이 아직 없고 충분히 쌓였으면 후보 제시
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

    # -----------------------------
    # 주기 루프: 요약/안건 변경감지/의견정리
    # -----------------------------
    async def _periodic_loop(self):
        self._last_summary_at = time.time()
        self._last_topic_check_at = time.time()
        self._last_opinion_flush_at = time.time()

        while self._running:
            try:
                await asyncio.sleep(0.5)
                now = time.time()

                # 1) 주기 요약
                if self.current_agenda and (now - self._last_summary_at >= self.summary_interval_sec):
                    await self._emit_progress_summary()
                    self._last_summary_at = now

                # 2) 안건 변경 감지 (LLM 기반 + 휴리스틱)
                if self.current_agenda and (now - self._last_topic_check_at >= self.topic_check_interval_sec):
                    await self._check_topic_shift()
                    self._last_topic_check_at = now

                # 3) 의견/정리 flush
                if self.current_agenda and (now - self._last_opinion_flush_at >= self.opinion_flush_interval_sec):
                    await self._flush_opinions_and_updates()
                    self._last_opinion_flush_at = now

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[F4] periodic error: {e}")

    # -----------------------------
    # 텍스트 윈도우 만들기
    # -----------------------------
    def _window_text(self, seconds: Optional[int] = None) -> str:
        if not self._recent_lines:
            return ""
        now = time.time()
        items = list(self._recent_lines)
        if seconds is not None:
            items = [x for x in items if (now - x[0]) <= seconds]
        # 너무 길면 최근 위주로 자르기
        tail = items[-120:]  # 안전 상한
        return "\n".join([f"[{spk}] {txt}" for _, spk, txt in tail])

    # -----------------------------
    # 1) 특정 시간마다 요약: "~~~하는 중입니다"
    # -----------------------------
    async def _emit_progress_summary(self):
        w = self._window_text(seconds=self.summary_interval_sec * 2)
        if not w.strip():
            return

        agenda = self.current_agenda.title if self.current_agenda else "알 수 없음"
        system = "너는 실시간 회의 서기다. 과장 없이, 현재 진행 상태를 한 문장으로 보고한다."
        user = (
            f"현재 안건: {agenda}\n\n"
            f"최근 전사:\n{w}\n\n"
            "요구:\n"
            "- 한국어 한 문장\n"
            "- 반드시 '...하는 중입니다' 형태\n"
            "- 안건을 명시\n"
        )
        schema = '{"progress": "현재 ~~ 안건에 대해 ~~하는 중입니다."}'

        out = await self.llm.json_call(system, user, schema)
        if out and isinstance(out, dict) and out.get("progress"):
            progress = str(out["progress"]).strip()
        else:
            # fallback: 단순 휴리스틱
            progress = f"현재 '{agenda}' 안건에 대해 논의하는 중입니다."

        print(f"\n[F4][진행요약 {now_hhmm()}] {progress}\n")

        # 누적 요약에도 반영(짧게)
        if self.current_agenda:
            if self.current_agenda.running_summary:
                self.current_agenda.running_summary += " " + progress
            else:
                self.current_agenda.running_summary = progress

    # -----------------------------
    # 2) 안건 후보 제시/선택 (3개 후보)
    # -----------------------------
    async def _propose_and_choose_agenda(self, reason: str):
        if self._awaiting_agenda_choice:
            return

        # 너무 자주 후보 띄우지 않게
        now = time.time()
        if now - self._last_propose_at < 15:
            return
        self._last_propose_at = now

        w = self._window_text(seconds=180)
        if not w.strip():
            return

        self._awaiting_agenda_choice = True
        try:
            candidates = await self._propose_agenda_candidates(w)
            if not candidates:
                candidates = self._fallback_candidates(w)

            chosen = await self._ask_user_choose_agenda(candidates, reason=reason)

            # 새 안건으로 전환
            await self._switch_agenda(chosen, reason=reason)

        finally:
            self._awaiting_agenda_choice = False

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
        # 간단 휴리스틱: 많이 나오는 명사/키워드 기반(아주 단순)
        # (외부 라이브러리 없이)
        words = re.findall(r"[가-힣A-Za-z0-9]{2,}", window_text)
        freq = defaultdict(int)
        for w in words:
            freq[w] += 1
        top = sorted(freq.items(), key=lambda kv: (-kv[1], -len(kv[0])))[:12]
        base = [w for w, _ in top]
        # 3개 후보 만들기
        c1 = base[0] if len(base) > 0 else "진행사항"
        c2 = base[1] if len(base) > 1 else "이슈정리"
        c3 = base[2] if len(base) > 2 else "다음액션"
        return [c1, c2, c3]

    async def _ask_user_choose_agenda(self, candidates: List[str], reason: str) -> str:
        # 사용자 입력은 블로킹이므로 to_thread
        def _input_choice() -> str:
            print("\n" + "=" * 62)
            print(f"[F4] 안건 후보 제안 ({reason})")
            for i, c in enumerate(candidates, 1):
                print(f"  {i}) {c}")
            print("  0) (직접 입력)")
            print("=" * 62)
            while True:
                s = input("[F4] 지금 안건 번호 선택 (1-3, 0=직접입력): ").strip()
                if s in ("1", "2", "3"):
                    return candidates[int(s) - 1]
                if s == "0":
                    t = input("[F4] 안건 제목 직접 입력: ").strip()
                    if t:
                        return t
                print("[F4] 입력이 올바르지 않습니다.")

        return await asyncio.to_thread(_input_choice)

    async def _switch_agenda(self, title: str, reason: str):
        title = (title or "").strip()
        if not title:
            return

        # 동일 안건이면 무시
        if self.current_agenda and self.current_agenda.title == title:
            return

        # 기존 안건 마감 전 flush
        if self.current_agenda:
            await self._flush_opinions_and_updates()
            self.agenda_history.append(self.current_agenda)

        self.current_agenda = AgendaItem(title=title)

        print(f"\n[F4][안건전환 {now_hhmm()}] '{title}' (사유: {reason})\n")

    # -----------------------------
    # 2) 안건 변경 감지
    # -----------------------------
    async def _check_topic_shift(self):
        # 최근 텍스트가 너무 없으면 스킵
        w = self._window_text(seconds=120)
        if not w.strip() or not self.current_agenda:
            return

        # 휴리스틱: 특정 전환 신호
        shift_signals = ("다음", "그럼", "넘어가", "전환", "또", "추가로", "마지막으로", "다른 건")
        if any(sig in w for sig in shift_signals):
            # LLM로 최종 판정
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

    # -----------------------------
    # 3) 안건에 대한 의견/결정/할일 추출해서 정리
    # -----------------------------
    async def _flush_opinions_and_updates(self):
        if not self.current_agenda:
            return

        # 최근 3~5분을 대상으로 정리(너무 길면 비용↑)
        w = self._window_text(seconds=300)
        if not w.strip():
            return

        agenda = self.current_agenda.title

        system = (
            "너는 회의 서기다. 특정 안건에 대한 발언에서 '의견', '결정', '할일'을 구조화한다.\n"
            "모호하면 과장하지 말고, 원문 근거가 약하면 제외한다."
        )
        user = (
            f"안건: {agenda}\n\n"
            f"전사:\n{w}\n\n"
            "요구:\n"
            "1) opinions_by_speaker: 화자별로 '의견/주장/제안'을 짧은 불릿으로 최대 3개\n"
            "2) decisions: 합의/결정된 문장만\n"
            "3) todos: 해야 할 일을 구체적으로(담당자 추정 가능하면 포함)\n"
            "4) agenda_summary: 이 안건에서 지금까지 핵심을 2~3문장 요약\n"
        )
        schema = """
        {
          "agenda_summary": "string",
          "opinions_by_speaker": {
            "speaker": ["opinion1", "opinion2"]
          },
          "decisions": ["..."],
          "todos": ["..."]
        }
        """.strip()

        out = await self.llm.json_call(system, user, schema)

        if not out:
            # fallback: 최소한의 정리(화자별 마지막 발언)
            self._fallback_flush(w)
            return

        agenda_summary = str(out.get("agenda_summary", "")).strip()
        opinions_by_speaker = out.get("opinions_by_speaker") or {}
        decisions = out.get("decisions") or []
        todos = out.get("todos") or []

        # 누적 반영
        if agenda_summary:
            self.current_agenda.running_summary = agenda_summary

        if isinstance(opinions_by_speaker, dict):
            for spk, lst in opinions_by_speaker.items():
                if not isinstance(lst, list):
                    continue
                for it in lst[:3]:
                    s = str(it).strip()
                    if s:
                        self.current_agenda.opinions_by_speaker[str(spk)].append(s)

        for d in decisions:
            s = str(d).strip()
            if s and s not in self.current_agenda.decisions:
                self.current_agenda.decisions.append(s)

        for t in todos:
            s = str(t).strip()
            if s and s not in self.current_agenda.todos:
                self.current_agenda.todos.append(s)

        # 출력
        self._print_agenda_snapshot()

    def _fallback_flush(self, window_text: str):
        if not self.current_agenda:
            return
        # 화자별 마지막 1~2문장만 추려서 "의견 후보"로 저장
        last_by = {}
        for line in window_text.splitlines():
            spk, txt = parse_transcript_line(line)
            if txt:
                last_by[spk] = txt

        for spk, txt in list(last_by.items())[:5]:
            self.current_agenda.opinions_by_speaker[spk].append(txt[:120])

        self._print_agenda_snapshot(fallback=True)

    def _print_agenda_snapshot(self, fallback: bool = False):
        ag = self.current_agenda
        if not ag:
            return

        tag = "FALLBACK" if fallback else "UPDATE"
        print("\n" + "-" * 70)
        print(f"[F4][{tag} {now_hhmm()}] 안건: {ag.title}")
        if ag.running_summary:
            print(f"요약: {ag.running_summary}")

        if ag.decisions:
            print("결정:")
            for x in ag.decisions[-5:]:
                print(f"  - {x}")

        if ag.todos:
            print("할일:")
            for x in ag.todos[-8:]:
                print(f"  - {x}")

        if ag.opinions_by_speaker:
            print("의견(화자별):")
            # 최근 것 위주로
            for spk, lst in list(ag.opinions_by_speaker.items())[:8]:
                recent = lst[-3:]
                for op in recent:
                    print(f"  - {spk}: {op}")
        print("-" * 70 + "\n")

    # 상태 스냅샷
    def get_state(self) -> dict:
        ag = self.current_agenda
        state = {
            "ts": time.time(),
            "current_agenda": {},
            "agenda_history": [],
            "recent_tail": [],
        }

        if ag:
            state["current_agenda"] = {
                "title": ag.title,
                "started_at": ag.started_at,
                "running_summary": ag.running_summary,
                "decisions": ag.decisions[-10:],
                "todos": ag.todos[-15:],
                "opinions_by_speaker": {
                    spk: lst[-5:] for spk, lst in ag.opinions_by_speaker.items()
                },
            }

        # 최근 전사 일부(화면용)
        tail = list(self._recent_lines)[-30:]
        state["recent_tail"] = [
            {"t": ts, "speaker": spk, "text": txt} for (ts, spk, txt) in tail
        ]

        # 완료 안건 히스토리 요약
        for old in self.agenda_history[-10:]:
            state["agenda_history"].append({
                "title": old.title,
                "started_at": old.started_at,
                "running_summary": old.running_summary,
                "decisions": old.decisions[-5:],
                "todos": old.todos[-8:],
            })

        return state
