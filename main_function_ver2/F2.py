import os
import sys
import numpy as np
import pyaudio
import datetime
import torch
import json
import asyncio
from dotenv import load_dotenv
import whisper
import threading
from huggingface_hub import login
from rx.core import Observer
import wave
from collections import deque

# Gemini API
from google import genai
from google.genai import types

# 화자 분리용 diart
from diart import SpeakerDiarization, SpeakerDiarizationConfig
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

# VAD 설정
VAD_THRESHOLD = 0.5 # 소리 임계값
VAD_MIN_SILENCE_MS = 500 # 침묵시간
VAD_SPEECH_PAD_MS = 120 # 발화 패딩 (가끔 말 시작하고 좀 늦게 감지할때가 있어서)

MIN_UTT_SEC = 0.6 # 최소 한 문장 길이
MAX_UTT_SEC = 25.0 # 최대 한 문장 길이
DBG_STT = True

# 경로 설정
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(CURRENT_DIR, "../log")

# -------------------- 디버그용 클래스 --------------------
class DebugObserver(Observer):
    def on_next(self, value):
        print("[DBG] observer on_next (diart emitted)")

    def on_error(self, error):
        print("[DBG] observer on_error:", repr(error))

    def on_completed(self):
        print("[DBG] observer on_completed")
        
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

        # diart 관례: (channels, samples)
        if wav.ndim == 1:
            wav = wav[None, :]
        elif wav.ndim == 2:
            # (N,1) -> (1,N)로 정규화
            if wav.shape[1] == 1 and wav.shape[0] != 1:
                wav = wav.T
            # 다채널이면 첫 채널만
            if wav.shape[0] > 1:
                wav = wav[:1, :]

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
            config = SpeakerDiarizationConfig(
                # Set the segmentation model used in the paper
                device=DEVICE,
                sample_rate=SAMPLE_RATE,
            )

            self.diar_pipeline = SpeakerDiarization(config)
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
            self.diar_inference.attach_observers(DebugObserver())
            print("다이얼 인퍼런스")
            # inference를 백그라운드 스레드로 실행
            threading.Thread(target=self._run_diar_inference, daemon=True).start()
            print("스레딩 스레드")
            print(" >> Diart 로드 완료!")
        except Exception as e:
            print(f"[Error] diart 로드 실패: {e}")
            sys.exit(1)
            
        # 4. Silero VAD 로드
        print(" [Local] Silero VAD 로드 중...")
        try:
            self.vad_model, self.vad_utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                trust_repo=True
            )
            (self.get_speech_timestamps,
             self.save_audio,
             self.read_audio,
             self.VADIterator,
             self.collect_chunks) = self.vad_utils

            self.vad_model.eval()
            self.vad_iter = self.VADIterator(
                self.vad_model,
                threshold=VAD_THRESHOLD,
                sampling_rate=SAMPLE_RATE,
                min_silence_duration_ms=VAD_MIN_SILENCE_MS,
                speech_pad_ms=VAD_SPEECH_PAD_MS
            )
            print(" >> Silero VAD 로드 완료!")
        except Exception as e:
            print(f"[Error] Silero VAD 로드 실패: {e}")
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

        # --- STT에 사용된 오디오 세그먼트 저장용 ---
        self.audio_segments_dir = os.path.join(LOGS_DIR, "segments")
        os.makedirs(self.audio_segments_dir, exist_ok=True)

        # 세그먼트 메타데이터는 JSONL로 누적 기록
        self.segment_index_path = os.path.join(self.audio_segments_dir, "segments.jsonl")
        self._segment_seq = 0

        # diart segment 중복 STT 방지
        self._last_processed_end = 0.0
        self._last_processed_lock = threading.Lock()

        # 스트림 시간 관리(샘플 카운터)
        self.total_samples = 0

        # 발화 버퍼 상태
        self.utt_active = False
        self.utt_start_sample = 0
        self.utt_buffer = []

        # diart timeline 저장(화자 타임라인만)
        self.timeline = deque(maxlen=20000)
        self.timeline_lock = threading.Lock()

        # STT 큐/워커
        self.stt_queue = asyncio.Queue()
        self.stt_worker_task = None

        # VAD 샘플 청크 채우기용
        self._vad_pending = np.zeros((0,), dtype=np.float32)

    # 전사 전 음성 파일 저장용
    def _save_segment_wav(self, seg_audio: np.ndarray, speaker: str, abs_start: float, abs_end: float) -> str:
        self._segment_seq += 1
        seg_id = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{self._segment_seq:06d}"
        wav_name = f"{seg_id}__{speaker}__{abs_start:.2f}-{abs_end:.2f}.wav"
        wav_path = os.path.join(self.audio_segments_dir, wav_name)

        x = np.asarray(seg_audio, dtype=np.float32)
        x = np.clip(x, -1.0, 1.0)
        pcm16 = (x * 32767.0).astype(np.int16)

        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm16.tobytes())

        return wav_path

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
        print("[DBG] diar inference thread started")
        try:
            # self.diar_source.read()를 호출하고
            # self.diar_source.stream에서 데이터가 emit 되면 pipeline이 처리
            self.diar_inference()
        except Exception as e:
            print(f"[DiarInference Error] {e}")
        finally:
            print("[DBG] diar inference thread exited")

    # 변경사항: STT를 여기서 진행하는게 아니라 화자 타임라인만 누적하는걸로 변경
    def _diar_hook(self, result):
        print("[DBG] _diar_hook called")
        try:
            annotation, ann_wav = result
            print("[DBG] ann_wav type:", type(ann_wav))
        except Exception:
            return

        try:
            if isinstance(ann_wav, SlidingWindowFeature):
                data = ann_wav.data
                sw = ann_wav.sliding_window
                print("[DBG] ann_wav.data type:", type(data), "shape:", getattr(data, "shape", None), "ndim:",
                      getattr(data, "ndim", None))
                print("[DBG] sliding_window start/duration/step:", float(getattr(sw, "start", 0.0)),
                      float(getattr(sw, "duration", 0.0)), float(getattr(sw, "step", 0.0)))
        except Exception as e:
            print("[DBG] ann_wav inspect error:", e)

        items = []
        try:
            for segment, _track, label in annotation.itertracks(yield_label=True):
                s = float(segment.start)
                e = float(segment.end)
                if e <= s:
                    continue
                items.append((s, e, str(label)))
        except Exception:
            return

        if not items:
            return
        items.sort(key=lambda x: x[0])

        with self.timeline_lock:
            for s, e, spk in items:
                self.timeline.append((s, e, spk))

    # 발화구간에 대해서 화자 결정하는 함수
    def _assign_speaker_by_overlap(self, u0: float, u1: float) -> str:
        if u1 <= u0:
            return "Unknown"

        with self.timeline_lock:
            tl = list(self.timeline)

        scores = {}
        for s, e, spk in tl:
            ov = max(0.0, min(u1, e) - max(u0, s))
            if ov > 0:
                scores[spk] = scores.get(spk, 0.0) + ov

        if not scores:
            return "Unknown"

        best_spk = max(scores.items(), key=lambda kv: kv[1])[0]
        best_ov = scores[best_spk]
        if best_ov < 0.30 * (u1 - u0):
            return "Unknown"
        return best_spk

    # 발화 구간 구분해서 오디오 반환함수
    def _vad_process_frame(self, frame: np.ndarray):
        x = torch.from_numpy(frame)
        event = self.vad_iter(x)

        if DBG_STT:
            # 입력 sanity: 길이/진폭
            m = float(np.max(np.abs(frame))) if len(frame) else 0.0
            print(f"[DBG] VAD in: len={len(frame)} max_abs={m:.4f} total_samples={self.total_samples}")

        print("[DBG] VAD raw event:", event)

        # 발화 중인 경우에만 버퍼 누적
        if event is None:
            if self.utt_active:
                self.utt_buffer.append(frame)
            return None

        if "start" in event:
            self.utt_active = True
            # 현재 시작 지점 근사
            self.utt_start_sample = max(0, self.total_samples - len(frame))
            self.utt_buffer = [frame]
            return None

        if "end" in event:
            if not self.utt_active:
                return None
            self.utt_buffer.append(frame)
            self.utt_active = False

            audio = np.concatenate(self.utt_buffer, axis=0) if self.utt_buffer else None
            self.utt_buffer = []
            if audio is None:
                return None

            dur = len(audio) / SAMPLE_RATE
            if dur < MIN_UTT_SEC:
                return None

            t0 = self.utt_start_sample / SAMPLE_RATE
            t1 = self.total_samples / SAMPLE_RATE

            # 너무 길면 MAX_UTT_SEC로 잘라서 여러 조각으로
            if dur > MAX_UTT_SEC:
                out = []
                step = int(MAX_UTT_SEC * SAMPLE_RATE)
                start = 0
                while start < len(audio):
                    end = min(len(audio), start + step)
                    seg = audio[start:end]
                    seg_t0 = t0 + (start / SAMPLE_RATE)
                    seg_t1 = t0 + (end / SAMPLE_RATE)
                    if (seg_t1 - seg_t0) >= MIN_UTT_SEC:
                        out.append((seg, seg_t0, seg_t1))
                    start = end
                return out

            return [(audio, t0, t1)]

        return None

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
    # 큐에 발화들 STT -> 화자 결정 -> 나머지 저장 분석등 처리
    async def _stt_worker(self):
        print("[DBG] _stt_worker started")
        while self.is_running:
            item = await self.stt_queue.get()
            if DBG_STT:
                print("[DBG] _stt_worker got item:", None if item is None else (len(item[0]), item[1], item[2]))
            if item is None:
                self.stt_queue.task_done()
                break
                
            audio_np, t0, t1 = item
            text = await asyncio.to_thread(self._run_whisper, audio_np)
            if not text:
                self.stt_queue.task_done()
                continue

            speaker = self._assign_speaker_by_overlap(t0, t1)

            # 오디오 저장용
            wav_path = self._save_segment_wav(audio_np, speaker, t0, t1)
            meta = {
                "time": datetime.datetime.now().isoformat(),
                "speaker": speaker,
                "segment_start": float(t0),
                "segment_end": float(t1),
                "wav_path": wav_path,
                "text": text,
            }
            with open(self.segment_index_path, "a", encoding="utf-8") as jf:
                jf.write(json.dumps(meta, ensure_ascii=False) + "\n")

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

            self.stt_queue.task_done()

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

        # STT 워커 시작
        self.stt_worker_task = asyncio.create_task(self._stt_worker())

        while self.is_running:
            try:
                data = await asyncio.to_thread(self.stream.read, CHUNK, False)

                # int16 PCM -> float32 [-1, 1]
                frame = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0

                # diart로 언제나 연속으로 넘기기
                self.diar_source.push_audio(frame)

                self._vad_pending = np.concatenate([self._vad_pending, frame], axis=0)

                VAD_FRAME = 512
                while len(self._vad_pending) >= VAD_FRAME:
                    sub = self._vad_pending[:VAD_FRAME]
                    self._vad_pending = self._vad_pending[VAD_FRAME:]

                    # VAD로 발화 확정
                    utts = self._vad_process_frame(sub)

                    # 발화 확정되면 STT
                    if utts:
                        for (audio_np, t0, t1) in utts:
                            if DBG_STT:
                                print(f"[DBG] stt_queue.put: len={len(audio_np)} t0={t0:.3f} t1={t1:.3f}")
                            await self.stt_queue.put((audio_np, t0, t1))

                # 시간 업데이트
                self.total_samples += VAD_FRAME

                await asyncio.sleep(0.001)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print("[ERR] main loop:", repr(e))
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
            if hasattr(self, "stt_queue"):
                asyncio.get_event_loop().create_task(self.stt_queue.put(None))
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