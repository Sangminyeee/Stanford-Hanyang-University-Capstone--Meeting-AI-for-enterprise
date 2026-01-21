# run_F2_F4.py
import asyncio
import sys
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

    # F2 시작
    try:
        await assistant.start()
    finally:
        # F2가 끝나면 F4도 종료
        await flow_ai.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
