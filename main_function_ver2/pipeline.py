import asyncio
import sys
import signal
from typing import Callable, Any

from F2 import MeetingAssistant
from F4 import MeetingFlowAI


# F2에서 전사한거 append 할때마다 콜백
class ObservableList(list):
    def __init__(self, on_append: Callable[[Any], None], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_append = on_append

    def append(self, item):
        super().append(item)
        try:
            self._on_append(item)
        except Exception as e:
            # F4 오류나도 F2 계속 실행
            print(f"[run_F2_F4] ObservableList callback error: {e}", file=sys.stderr)


async def main():
    # F4
    flow_ai = MeetingFlowAI(
        summary_interval_sec=20,  # 1) 특정 시간마다 요약
        topic_check_interval_sec=20,  # 2) 안건 변경 감지 템포
        propose_min_lines=6,  # 안건 후보 띄우기 최소 라인 수
        opinion_flush_interval_sec=45  # 3) 의견 정리 주기
    )

    # F2
    assistant = MeetingAssistant()

    # F2 전사 append 할 때마다 F4로 전달되게 full_transcript를 ObservableList로 교체
    loop = asyncio.get_running_loop()

    def on_new_transcript_line(line: str):
        # F2의 append 이벤트루프 호출 방지
        loop.call_soon_threadsafe(flow_ai.push_transcript_line, line)

    assistant.full_transcript = ObservableList(on_new_transcript_line)

    # F4 백그라운드
    await flow_ai.start()

    # 키보드 인터럽트로 중간에 끊었을 때 다 처리하기용
    shutting_down = {"flag": False}

    # Ctrl+C 들어왔을 때 핸들러
    def _sigint_handler(signum, frame):
        # 1번째 Ctrl+C 되도록 정상종료
        if not shutting_down["flag"]:
            shutting_down["flag"] = True
            print("\n[pipeline] SIGINT received. Graceful shutdown requested...")
            try:
                assistant.is_running = False
            except Exception:
                pass
            return

        # 2번째 Ctrl+C는 강종
        print("\n[pipeline] SIGINT received again. Force exiting now.", file=sys.stderr)
        raise KeyboardInterrupt

    old_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _sigint_handler)

    # F2 시작
    try:
        await assistant.start()
    finally:
        # 핸들러 복구
        signal.signal(signal.SIGINT, old_handler)
        # F2가 끝나면 F4도 종료
        await flow_ai.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # 2번 눌러서 강종할때만 작동
        pass
