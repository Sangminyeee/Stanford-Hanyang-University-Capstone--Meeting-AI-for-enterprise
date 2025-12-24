import os
import sys
import numpy as np
import pyaudio
import datetime
import torch
import json
import asyncio
import math
import struct
from dotenv import load_dotenv
import whisper

# Gemini API
from google import genai
from google.genai import types

# 화자 분리용
from pyannote.audio import Model
from pyannote.audio.core.inference import Inference
from scipy.spatial.distance import cdist

# 초기 설정
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GEMINI_API_KEY:
    print("[ERROR] .env 파일에 GEMINI_API_KEY가 없습니다.")
    sys.exit(1)

# CUDA 설정
DEVICE = "cuda"
FP16_RUN = True

torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

# 오디오 설정
DEVICE_INDEX = 1  # 마이크 장치 번호 
SAMPLE_RATE = 16000
BUFFER_SIZE = 6  # 분석을 위해 모으는 문장 개수
WHISPER_MODEL_SIZE = "turbo" # 모델
GEMINI_MODEL_NAME = "gemini-3-flash-preview" # 제미니 모델

# VAD (음성 감지) 설정
SILENCE_THRESHOLD = 500
SILENCE_DURATION = 0.5
MIN_AUDIO_LEN = 0.3

# 경로 설정
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(CURRENT_DIR, "../log")


# -------------------- 메인 클래스 --------------------
class MeetingAssistant:
    def __init__(self):
        print("\n" + "=" * 60)
        print(f" [시스템 시작] Device: {DEVICE}")
        print("=" * 60)

        # 1. Gemini 연결
        print(f" [Cloud] Gemini ({GEMINI_MODEL_NAME}) 연결 중...")
        self.client = genai.Client(api_key=GEMINI_API_KEY)

        # 2. Whisper 로드 (OpenAI Original)
        print(f" [Local] STT 모델 (OpenAI Whisper {WHISPER_MODEL_SIZE}) 로드 중...")
        try:
            # download_model_local 함수 필요 없음. load_model이 알아서 함.
            # download_root를 지정하지 않으면 기본 캐시 폴더(~/.cache/whisper)에 저장됨
            self.stt_model = whisper.load_model(WHISPER_MODEL_SIZE, device=DEVICE)
            print(" >> Whisper 모델 로드 완료!")
        except Exception as e:
            print(f"[Error] Whisper 로드 실패: {e}")
            sys.exit(1)

        # 3. 화자 식별 모델 로드
        print(" [Local] 화자 식별 모델 (WeSpeaker) 로드 중...")
        try:
            self.embedding_model = Model.from_pretrained(
                "pyannote/wespeaker-voxceleb-resnet34-LM",
                use_auth_token=HF_TOKEN
            )
            self.inference = Inference(self.embedding_model, window="whole")
            self.inference.to(torch.device(DEVICE))
        except Exception as e:
            print(f"[Error] 화자 모델 로드 실패: {e}")
            sys.exit(1)

        print("\n >> 모든 기능 준비 완료 <<\n")

        # 상태 변수
        self.is_running = True
        self.meeting_topic = ""
        self.transcript_buffer = []
        self.full_transcript = []
        self.analysis_logs = []

        # 화자 식별 메모리
        self.speaker_bank = {}
        self.speaker_counter = 1
        self.SPEAKER_SIMILARITY_THRESHOLD = 0.6

    # 소리 크기 계산
    def get_rms(self, data):
        count = len(data) // 2
        shorts = struct.unpack("%dh" % count, data)
        sum_squares = sum(n * n for n in [s * (1.0 / 32768.0) for s in shorts])
        return math.sqrt(sum_squares / count) * 10000

    # -------------------- [Thread] AI 처리 함수들 --------------------
    # Whisper STT
    def _run_whisper(self, audio_np):
        try:
            result = self.stt_model.transcribe(audio_np, language="ko", fp16=FP16_RUN)
            return result['text'].strip()
        except Exception as e:
            print(f"Whisper Error: {e}")
            return ""

    # 화자 분리
    def _run_speaker_id(self, audio_np):
        try:
            if len(audio_np) / SAMPLE_RATE < 0.5: return "Unknown"

            audio_tensor = torch.from_numpy(audio_np).float().unsqueeze(0).to(DEVICE)
            embedding_result = self.inference({"waveform": audio_tensor, "sample_rate": SAMPLE_RATE})
            new_emb = embedding_result.cpu().numpy() if isinstance(embedding_result, torch.Tensor) else embedding_result

            if not self.speaker_bank:
                name = f"Speaker {self.speaker_counter}"
                self.speaker_bank[name] = new_emb
                self.speaker_counter += 1
                return name

            min_dist = 100.0
            best_match = None

            for name, saved_emb in self.speaker_bank.items():
                dist = cdist(new_emb.reshape(1, -1), saved_emb.reshape(1, -1), metric="cosine")[0][0]
                if dist < min_dist:
                    min_dist = dist
                    best_match = name

            if min_dist < (1 - self.SPEAKER_SIMILARITY_THRESHOLD):
                return best_match
            else:
                new_name = f"Speaker {self.speaker_counter}"
                self.speaker_bank[new_name] = new_emb
                self.speaker_counter += 1
                return new_name
        except Exception:
            return "Unknown"

    # 요약, 흐름, 결정사항 추출
    def _run_gemini_analysis(self, text_chunk, main_topic):
        prompt = f"""
        당신은 회의 서기입니다. 메인 주제는 "{main_topic}"입니다.
        입력된 회의 내용을 분석하여 아래 JSON 포맷으로 응답하세요.

        [입력 텍스트]
        {text_chunk}

        [요청 사항]
        1. summary: 내용을 요약하세요. (구현방안 3)
        2. current_flow: 현재 논의가 어떤 안건으로 흘러가고 있는지 한 줄로 설명하세요. (구현방안 4)
        3. decisions: 합의되거나 결정된 사항을 명시하세요. 없으면 빈 리스트. (구현방안 5)
        4. todos: 구체적인 할 일을 추출하세요.

        [출력 형식 (JSON Only)]
        {{
            "summary": "...",
            "current_flow": "현재 A안건에 대해 논의 중이며...",
            "decisions": ["결정사항1", ...],
            "todos": ["..."]
        }}
        """

        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            # JSON 클리닝
            clean_text = response.text.strip()
            if clean_text.startswith("```json"): clean_text = clean_text[7:]
            if clean_text.endswith("```"): clean_text = clean_text[:-3]
            return json.loads(clean_text)
        except Exception as e:
            print(f"[Gemini Error] {e}")
            return None

    # -------------------- [Async] 비동기 파이프라인 --------------------
    # Gemini request, 결과 출력
    async def analyze_task(self, full_text):
        result = await asyncio.to_thread(self._run_gemini_analysis, full_text, self.meeting_topic)

        if result:
            now = datetime.datetime.now().strftime("%H:%M")
            log_entry = {
                "time": now,
                "summary": result.get("summary", ""),
                "current_flow": result.get("current_flow", ""),
                "decisions": result.get("decisions", []),
                "todos": result.get("todos", [])
            }
            self.analysis_logs.append(log_entry)

            # --- 실시간 결과 출력 ---
            print(f"\n >>> [분석 {now}] --------------------")
            print(f"요약: {log_entry['summary']}")
            print(f"흐름: {log_entry['current_flow']}")
            if log_entry['decisions']:
                print(f"결정: {', '.join(log_entry['decisions'])}")
            if log_entry['todos']:
                print(f"할일: {', '.join(log_entry['todos'])}")
            print(" -----------------------------------------\n")

    # 오디오 프로세스 파이프라인 (STT -> 화자식별 -> 버퍼링 -> 분석 트리거)
    async def process_audio(self, audio_np):
        try:
            # 1. STT 실행
            text_chunk = await asyncio.to_thread(self._run_whisper, audio_np)
            if not text_chunk or len(text_chunk) < 2: return

            # [중복 방지 로직]
            if self.full_transcript:
                last_log = self.full_transcript[-1]
                if "]" in last_log:
                    last_text = last_log.split("]", 1)[1].strip()
                    if text_chunk == last_text: return

            # 2. 화자 식별 실행
            speaker = await asyncio.to_thread(self._run_speaker_id, audio_np)

            # 로그 출력 및 저장
            log_text = f"[{speaker}] {text_chunk}"
            print(f" {log_text}")

            self.full_transcript.append(log_text)
            self.transcript_buffer.append(log_text)

            # 3. 버퍼가 차면 분석 요청
            if len(self.transcript_buffer) >= BUFFER_SIZE:
                chunk_to_analyze = "\n".join(self.transcript_buffer)
                self.transcript_buffer = []
                asyncio.create_task(self.analyze_task(chunk_to_analyze))

        except Exception as e:
            print(f"프로세싱 에러: {e}")

    # -------------------- 메인 루프 --------------------
    async def start(self):
        self.meeting_topic = input("\n회의 주제를 입력하세요: ")
        if not self.meeting_topic: self.meeting_topic = "자유 회의"

        CHUNK = int(SAMPLE_RATE * 0.1)
        self.p = pyaudio.PyAudio()

        try:
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                input=True,
                input_device_index=DEVICE_INDEX,
                frames_per_buffer=CHUNK
            )
        except:
            print(f"장치 {DEVICE_INDEX} 오류. 기본 장치로 시작합니다.")
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK
            )

        print(f"\n녹음 시작: '{self.meeting_topic}' (Ctrl+C로 종료)\n")

        audio_buffer = []
        silence_chunks = 0
        is_speaking = False

        while self.is_running:
            try:
                data = self.stream.read(CHUNK, exception_on_overflow=False)
                rms = self.get_rms(data)

                # VAD 로직
                if rms > SILENCE_THRESHOLD:
                    is_speaking = True
                    silence_chunks = 0
                    audio_buffer.append(data)
                else:
                    if is_speaking:
                        audio_buffer.append(data)
                        silence_chunks += 1
                        if silence_chunks * 0.1 > SILENCE_DURATION:
                            is_speaking = False
                            if len(audio_buffer) * 0.1 >= MIN_AUDIO_LEN:
                                full_audio = b''.join(audio_buffer)
                                audio_np = np.frombuffer(full_audio, dtype=np.int16).astype(np.float32) / 32768.0
                                asyncio.create_task(self.process_audio(audio_np))
                            audio_buffer = []
                            silence_chunks = 0
                await asyncio.sleep(0.001)

            except KeyboardInterrupt:
                break
            except Exception:
                continue

        self._cleanup()

    def _cleanup(self):
        print("\n종료 및 저장 중...")
        self.is_running = False
        if hasattr(self, 'stream'):
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()
        self.save_report()

    def save_report(self):
        if not os.path.exists(LOGS_DIR): os.makedirs(LOGS_DIR)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M')
        filename = f"meeting_result_{timestamp}.txt"
        path = os.path.join(LOGS_DIR, filename)

        with open(path, "w", encoding="utf-8") as f:
            f.write(f"회의 주제: {self.meeting_topic}\n")
            f.write(f"일시: {timestamp}\n")
            f.write("=" * 50 + "\n\n")

            f.write("[1. 회의 흐름 및 분석]\n")
            for log in self.analysis_logs:
                f.write(f"[{log['time']}]\n")
                f.write(f"  - 요약: {log['summary']}\n")
                f.write(f"  - 흐름: {log['current_flow']}\n")
                if log['decisions']: f.write(f"  - 결정: {', '.join(log['decisions'])}\n")
                if log['todos']: f.write(f"  - 할일: {', '.join(log['todos'])}\n\n")

            f.write("=" * 50 + "\n")
            f.write("[2. 전체 스크립트]\n")
            for line in self.full_transcript:
                f.write(f"{line}\n")

        print(f"저장 완료: {path}")


if __name__ == "__main__":
    assistant = MeetingAssistant()
    try:
        asyncio.run(assistant.start())
    except KeyboardInterrupt:
        assistant._cleanup()