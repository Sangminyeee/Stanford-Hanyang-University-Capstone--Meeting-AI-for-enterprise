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
import threading
import time
import queue
from huggingface_hub import login

# Gemini API
from google import genai
from google.genai import types

# 화자 분리용 diart
from diart import SpeakerDiarization
from diart.inference import StreamingInference
from diart.sources import AudioSource
from pyannote.core import SlidingWindowFeature

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

# -------------------- 오디오 주입 클래스 --------------------
# numpy waveform을 push_audio()로 주입하면 diart의 StreamingInference가 read()로 블록된 상태에서도 stream을 통해 데이터 수신
class PushAudioSource(AudioSource):
    def __init__(self, uri: str = "push", sample_rate: int = 16000):
        super().__init__(uri=uri, sample_rate=sample_rate)
        self._close_event = threading.Event()
        self._closed = False

    def read(self):
        self._close_event.wait()

    def push_audio(self, waveform: np.ndarray):
        if waveform is None or self._closed:
            return

        wav = np.asarray(waveform, dtype=np.float32)
        print("[DBG] on_next", wav.shape)

        # diart 관례: (channels, samples)
        if wav.ndim == 1:
            wav = np.expand_dims(wav, axis=0)  # (1, N)
        elif wav.ndim == 2:
            # (N,1) -> (1,N)로 정규화
            if wav.shape[1] == 1 and wav.shape[0] != 1:
                wav = wav.T
            # 다채널이면 첫 채널만
            if wav.shape[0] > 1:
                wav = wav[:1, :]

        # 핵심: rx subject로 흘려보내기
        self.stream.on_next(wav)

    def close(self):
        if not self._closed:
            self._closed = True
            try:
                self.stream.on_completed()
            except Exception:
                pass
            self._close_event.set()


# -------------------- 메인 클래스 --------------------
class MeetingAssistant:
    def __init__(self):
        print("\n" + "=" * 60)
        print(f" [시스템 시작] Device: {DEVICE}")
        print("=" * 60)
        login(token = HF_TOKEN)

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
        print(" [Local] diart SpeakerDiarization 파이프라인 로드 중...")
        try:
            self.diar_pipeline = SpeakerDiarization()
            # push 소스 생성
            self.diar_source = PushAudioSource(sample_rate=SAMPLE_RATE)
            self.diar_inference = StreamingInference(
                self.diar_pipeline,
                self.diar_source,
                do_plot=False,
                show_progress=False,
            )
            # 다이얼 결과 수신용
            self.diar_inference.attach_hooks(self._diar_hook)
            print("다이얼 인퍼런스")
            # inference를 백그라운드 스레드로 실행
            threading.Thread(target=self._run_diar_inference, daemon=True).start()
            print("스레딩 스레드")
            print(" >> Diart 로드 완료!")
        except Exception as e:
            print(f"[Error] diart 로드 실패: {e}")
            sys.exit(1)

        print("\n >> 모든 기능 준비 완료 <<\n")

        # 상태 변수
        self.is_running = True
        self.meeting_topic = ""
        self.transcript_buffer = []
        self.full_transcript = []
        self.analysis_logs = []
        self._transcript_lock = threading.Lock()

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
    def _run_diar_inference(self):
        try:
            # self.diar_source.read()를 호출하고
            # self.diar_source.stream에서 데이터가 emit 되면 pipeline이 처리
            self.diar_inference()
        except Exception as e:
            print(f"[DiarInference Error] {e}")

    # diart에서 받은 화자 분리된 발화 구간들 whisper로 전사 후 분석
    def _diar_hook(self, result):
        try:
            annotation, ann_wav = result
        except Exception:
            return

        # waveform 탐색
        waveform = None
        wav_start_time = 0.0
        try:
            if isinstance(ann_wav, SlidingWindowFeature):
                # ann_wav.data: (num_samples, num_channels?) 또는 (num_samples,) 형태일 수 있음
                data = ann_wav.data
                wav_start_time = float(getattr(ann_wav.sliding_window, "start", 0.0))
                if isinstance(data, np.ndarray):
                    if data.ndim == 2:
                        # (N, 1) -> (N,)
                        if data.shape[1] == 1:
                            waveform = data[:, 0]
                        # (1, N) -> (N,)
                        elif data.shape[0] == 1:
                            waveform = data[0, :]
                        else:
                            # 다채널이면 첫 채널만 사용(간단 처리)
                            waveform = data[:, 0]
                    elif data.ndim == 1:
                        waveform = data
            elif isinstance(ann_wav, np.ndarray):
                # 혹시 ndarray로 올 때도 처리
                if ann_wav.ndim == 2:
                    waveform = ann_wav[0, :] if ann_wav.shape[0] == 1 else ann_wav[:, 0]
                elif ann_wav.ndim == 1:
                    waveform = ann_wav
        except Exception:
            waveform = None

        if waveform is None:
            return

        # annotation에서 각 발화 구간, 라벨 얻어서 Whisper로 전사 후 분석
        try:
            for segment, track, label in annotation.itertracks(yield_label=True):
                speaker = str(label)

                # segment 시간은 "전체 스트림 기준"인 경우가 많아서,
                # 현재 chunk(ann_wav)의 시작 시간(wav_start_time) 기준으로 상대좌표로 변환해 slice
                rel_start = float(segment.start) - wav_start_time
                rel_end = float(segment.end) - wav_start_time

                # chunk 밖으로 나가면 클램프
                rel_start = max(0.0, rel_start)
                rel_end = max(rel_start, rel_end)

                start_idx = int(rel_start * SAMPLE_RATE)
                end_idx = int(rel_end * SAMPLE_RATE)
                end_idx = min(len(waveform), end_idx)

                seg_audio = waveform[start_idx:end_idx]

                # 짧은 길이는 생략
                if len(seg_audio) < int(0.2 * SAMPLE_RATE):
                    continue

                # Whisper 보내기 위한 포맷 변환
                text = self._run_whisper(seg_audio)

                if not text:
                    continue

                log_text = f"[{speaker}] {text}"
                with self._transcript_lock:
                    self.full_transcript.append(log_text)
                    print(f" {log_text}")

                # 분석 버퍼
                self.transcript_buffer.append(log_text)
                if len(self.transcript_buffer) >= BUFFER_SIZE:
                    chunk_to_analyze = "\n".join(self.transcript_buffer)
                    self.transcript_buffer = []
                    asyncio.create_task(self.analyze_task(chunk_to_analyze))
        except Exception as e:
            print(f"_diar_hook 처리 에러: {e}")

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

    # 오디오 프로세스 파이프라인 (Diart(화자구분) -> STT(Whisper))
    # Diart로 화자분리하려면 audio chunk를 diart 소스로 push해야함
    # STT -> 화자식별 이었던 기존에서 diart에서 분리한 구간을 받아 whisper로 전사하도록 개조
    async def process_audio(self, audio_np):
        if audio_np is None:
            print("[DBG] audio_np is None")
            return
        print("[DBG] process_audio len(sec)=", len(audio_np) / SAMPLE_RATE)

        self.diar_source.push_audio(audio_np)
        print("[DBG] pushed to diar_source")
        try:
            # 최소 길이 체크
            if audio_np is None or len(audio_np) / SAMPLE_RATE < 0.2:
                return

            # diart에 waveform push (float32, -1..1)
            try:
                if hasattr(self, 'diar_source'):
                    self.diar_source.push_audio(audio_np)
                else:
                    # diart가 없다면 기존 동작: Whisper 바로 실행 + 임시 스피커 id
                    text_chunk = await asyncio.to_thread(self._run_whisper, audio_np)
                    if not text_chunk or len(text_chunk) < 2: return
                    speaker = "Unknown"
                    log_text = f"[{speaker}] {text_chunk}"
                    with self._transcript_lock:
                        self.full_transcript.append(log_text)
                        self.transcript_buffer.append(log_text)
            except Exception as e:
                print(f"diart push error: {e}")
        except Exception as e:
            print(f"process_audio 에러: {e}")

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
        # 기존 정리
        print("\n종료 및 저장 중...")
        self.is_running = False
        if hasattr(self, 'stream'):
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()
        # diart 소스 종료
        try:
            if hasattr(self, 'diar_source'):
                self.diar_source.close()
        except Exception:
            pass
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