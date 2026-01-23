import asyncio
import sys
import signal
from typing import Callable, Any

from F2 import MeetingAssistant
from F4 import MeetingFlowAI

# 시각화용
import threading
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

# 시각화용 서버
def start_state_server(flow_ai, assistant, loop, host="127.0.0.1", port=8765):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/state":
                try:
                    data = flow_ai.get_state()
                    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as e:
                    msg = json.dumps({"error": str(e)}).encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(msg)))
                    self.end_headers()
                    self.wfile.write(msg)
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path != "/choose_agenda":
                self.send_response(404)
                self.end_headers()
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length > 0 else b"{}"
                payload = json.loads(raw.decode("utf-8"))
                title = (payload.get("title") or "").strip()
                if not title:
                    raise ValueError("title is required")

                # assyncio 루프 위에 태스크 올리기
                loop.call_soon_threadsafe(lambda: asyncio.create_task(flow_ai.choose_agenda(title)))

                resp = json.dumps({"ok": True, "chosen": title}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            except Exception as e:
                msg = json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)
                
        def log_message(self, format, *args):
            # 기본 로그 끄기(원하면 삭제)
            return

    server = HTTPServer((host, port), Handler)
    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()
    print(f"[run_F2_F4] State server: http://{host}:{port}/state")
    return server

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
        summary_interval_sec=180,  # 1) 특정 시간마다 요약 (3분)
        summary_window_sec=180,  # 요약 컨텍스트 윈도우 (3분)
        live_min_interval_sec=180,  # 라이브 분석 최소 주기
        live_max_interval_sec=300,  # 라이브 분석 최대 주기
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
    state_server = start_state_server(flow_ai, assistant, loop, port=8765)

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
                state_server.shutdown()
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
