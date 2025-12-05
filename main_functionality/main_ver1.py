import os
import sys
import numpy as np
import pyaudio
import datetime
import torch
from dotenv import load_dotenv
import struct
import math
import asyncio
import json

# [AI 라이브러리]
from faster_whisper import WhisperModel
from google import genai
from google.genai import types

# [화자 분리 라이브러리]
from pyannote.audio import Model
from pyannote.audio.core.inference import Inference
from scipy.spatial.distance import cdist

# [UI 라이브러리]
from tqdm import tqdm

# 토큰 불러오기
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# TF32 가속
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

# 설정값
DEVICE_INDEX = 1  # 장치 번호
SAMPLE_RATE = 16000
BUFFER_SIZE = 6  # 묶어서 요약할 문장 수
FLOW_THRESHOLD = 3  # 주제 유사도 임계값
WHISPER_MODEL_SIZE = "medium"  # Whisper 모델 크기 (small, medium, large-v3)
GEMINI_MODEL_NAME = "gemini-2.5-flash"

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
MODELS_DIR = os.path.join(PARENT_DIR, "models")  # 모델 저장 폴더
LOGS_DIR = os.path.join(PARENT_DIR, "log")  # 로그 저장 폴더

# 침묵 감지
SILENCE_THRESHOLD = 500  # 최소 소리 (이거 넘어야 녹음됨)
SILENCE_DURATION = 0.3  # 몇초 이상 조용해야하는지
MIN_AUDIO_LEN = 0.8  # 최소 몇초 이상 말해야하는지

# CUDA 없으면 오류날 수 있음 주의!
DEVICE = "cuda"
COMPUTE_TYPE = "float16"

# 모델 다운로드하는 함수
def download_model_local(repo_id, local_dir):
    from huggingface_hub import hf_hub_download, list_repo_files

    model_name = repo_id
    save_path = os.path.join(local_dir, f"faster-whisper-{model_name}")
    repo_id = f"Systran/faster-whisper-{model_name}"

    # 로컬에 있는지 확인용
    if os.path.exists(save_path) and len(os.listdir(save_path)) > 0:
        print(f"\n모델 존재")
        return save_path

    # 폴더 파일 확인
    os.makedirs(save_path, exist_ok=True)
    try:
        files = list_repo_files(repo_id)
        target_files = [f for f in files if f.endswith((".bin", ".json", ".txt"))]
        # 모델 다운로드
        for filename in tqdm(target_files, desc=f"다운로드 중: {model_name}", unit="file"):
            hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=save_path,
                local_dir_use_symlinks=False
            )
    except Exception as e:
        print(f"[ERROR] 모델 다운로드 오류: {e}")
    return save_path


class MeetingAssistant:
    def __init__(self):
        # Whisper model 로드
        print("--------------------------------------------------")
        print("시작")
        print("환경:", DEVICE)
        print("--------------------------------------------------")

        # Gemini 연결
        print(f"LLM Gemini {GEMINI_MODEL_NAME} 연결")
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Whisper 모델
        print(f"STT 모델(Whisper {WHISPER_MODEL_SIZE}) 로드")
        try:
            model_path = download_model_local(WHISPER_MODEL_SIZE, MODELS_DIR)
            self.stt_model = WhisperModel(model_path, device=DEVICE, compute_type=COMPUTE_TYPE)
            print("Whisper 로드 완료")
        except Exception as e:
            print(f"Whisper 로드 실패: {e}")
            sys.exit(1)

        # 화자 임베딩 모델
        print("화자 임베딩 모델(wespeaker) 로드")
        try:
            self.embedding_model = Model.from_pretrained(
                "pyannote/wespeaker-voxceleb-resnet34-LM",
                use_auth_token=HF_TOKEN
            )
            self.inference = Inference(self.embedding_model, window="whole")
            self.inference.to(torch.device(DEVICE))
            print("화자 임베딩 모델(wespeaker) 로드 완료")
        except Exception as e:
            print(f"화자 임베딩 모델(wespeaker) 로드 실패: {e}")
            sys.exit(1)

        print("모든 모델 로드 완료")
        print("--------------------------------------------------\n")

        # 상태 변수
        self.is_running = True
        self.transcript_buffer = [] # Gemini 전송용 버퍼
        self.full_transcript = [] # 전체 대화 저장
        self.analysis_logs = [] # Gemini 분석 결과 저장
        self.meeting_topic = ""

        # 화자 기억용
        self.speaker_bank = {}  # 화자 벡터 저장해놓는거
        self.speaker_counter = 1
        self.SPEAKER_SIMILARITY_THRESHOLD = 0.5  # 화자 벡터끼리 유사도 임계값

    # 소리 크기 계산 함수
    def get_rms(self, data):
        count = len(data) // 2
        shorts = struct.unpack("%dh" % count, data)
        sum_squares = sum(n * n for n in [s * (1.0 / 32768.0) for s in shorts])
        return math.sqrt(sum_squares / count) * 10000

    # --------------------------------- 동기 실행용 ----------------------------------------

    # Whisper 추론함수
    def _run_whisper(self, audio_np):
        segments, _ = self.stt_model.transcribe(audio_np, beam_size=5, language="ko", condition_on_previous_text=False)
        return "".join([s.text + " " for s in segments]).strip()

    # 화자 식별 함수
    def _run_speaker_id(self, audio_np):
        try:
            if len(audio_np) / SAMPLE_RATE < 0.5:
                print("샘플레이트 문제")
                return "Unknown"

            audio_tensor = torch.from_numpy(audio_np).float().unsqueeze(0).to(DEVICE)
            embedding_result = self.inference({"waveform": audio_tensor, "sample_rate": SAMPLE_RATE})

            if isinstance(embedding_result, torch.Tensor):
                new_emb = embedding_result.cpu().numpy()
            else:
                new_emb = embedding_result

            # 화자 등록
            if not self.speaker_bank:
                name = f"Speaker {self.speaker_counter}"
                self.speaker_bank[name] = new_emb
                self.speaker_counter += 1
                return name
            
            # 화자 비교
            min_dist = 100.0
            best_match = None
            for name, saved_emb in self.speaker_bank.items():
                dist = cdist(new_emb.reshape(1, -1), saved_emb.reshape(1, -1), metric="cosine")[0][0]
                if dist < min_dist:
                    min_dist = dist
                    best_match = name

            if min_dist < self.SPEAKER_SIMILARITY_THRESHOLD:
                return best_match
            else:
                new_name = f"Speaker {self.speaker_counter}"
                self.speaker_bank[new_name] = new_emb
                self.speaker_counter += 1
                return new_name
        except Exception as e:
            print(f"화자 식별 오류: {e}")
            return "Unknown"
    
    # Gemini 요약, 결정사항, 주제 이탈 여부 요청 함수
    def _run_gemini_analysis(self, text_chunk, main_topic):
        prompt = f"""
        당신은 꼼꼼한 회의 서기입니다.
        현재 회의의 메인 주제는 "{main_topic}"입니다.
        아래 입력된 회의 스크립트 조각을 분석하여 다음 JSON 형식으로만 응답하세요. (마크다운 태그 없이 순수 JSON만 출력)

        [입력 텍스트]
        {text_chunk}

        [분석 가이드]
        1. summary: 대화 내용을 1~2문장으로 명확히 요약하세요.
        2. decisions: "하기로 했다", "결정했다", "그렇게 합시다" 등 합의된 결정 사항이 있다면 명시하세요. (없으면 빈 리스트 [])
        3. off_topic_score: 메인 주제("{main_topic}")와 현재 대화의 관련성을 0~10점으로 평가하세요. (0: 완전 무관, 10: 주제 그 자체)
        4. todos: "(담당자) 할일 내용" 형태로 구체적인 액션 아이템을 추출하세요.

        [출력 형식 (JSON)]
        {{
            "summary": "요약 내용...",
            "decisions": ["결정사항1", "결정사항2"],
            "off_topic_score": 9,
            "todos": ["(김철수) 리포트 작성", "(이영희) 서버 점검"]
        }}
        """

        try:
            # 요청 응답
            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )

            # JSON 파싱 전처리
            clean_text = response.text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            return json.loads(clean_text)

        except Exception as e:
            print(f"[Gemini Error] {e}")
            return None

    # --------------------------------- 비동기 실행용 ----------------------------------------
    async def analyze_task(self, full_text):
        result = await asyncio.to_thread(self._run_gemini_analysis, full_text, self.meeting_topic)

        if result:
            now = datetime.datetime.now().strftime("%H:%M")
            
            # 로그 저장
            log_entry = {
                "time": now,
                "summary": result.get("summary", ""),
                "decisions": result.get("decisions", []),
                "off_topic_score": result.get("off_topic_score", 10),
                "todos": result.get("todos", [])
            }
            self.analysis_logs.append(log_entry)

            print(f"요약: {log_entry['summary']}")

            if log_entry['decisions']:
                print(f"결정사항: {', '.join(log_entry['decisions'])}")

            if log_entry['todos']:
                print(f"할일: {', '.join(log_entry['todos'])}")

            # 주제 이탈 경고
            score = log_entry['off_topic_score']
            if score < FLOW_THRESHOLD:
                print(f"[Warning] 논점 이탈 감지 (유사도: {score}/10)")

    # 오디오 처리 파이프라인 (STT -> 화자 분리 -> 요약 -> 분석)
    async def process_audio(self, audio_np):
        try:
            # 1. Whisper 실행
            text_chunk = await asyncio.to_thread(self._run_whisper, audio_np)
            # 텍스트가 없거나 너무 짧으면 패스
            if not text_chunk or len(text_chunk) < 2: return 
            
            # 중복방지
            if self.full_transcript:
                last_log = self.full_transcript[-1]
                if "]" in last_log:
                    last_text_content = last_log.split("]", 1)[1].strip()
                    if text_chunk == last_text_content:
                        return

            # 2. 화자 식별
            speaker = await asyncio.to_thread(self._run_speaker_id, audio_np)
            
            # 3. 로그 출력
            log_text = f"[{speaker}] {text_chunk}"
            print(f"   {log_text}")

            self.full_transcript.append(log_text)
            self.transcript_buffer.append(text_chunk)

            # 4. 요약 조건 충족 시
            if len(self.transcript_buffer) >= BUFFER_SIZE:
                full_text = "\n".join(self.transcript_buffer)
                self.transcript_buffer = []
                # 5. 분석 작업을 백그라운드 태스크로
                asyncio.create_task(self.analyze_task(full_text))

        except Exception as e:
            print(f"처리 에러: {e}")

    # --------------------------------- 메인 ----------------------------------------
    async def start(self):
        self.meeting_topic = input("회의 주제: ")
        if not self.meeting_topic: self.meeting_topic = "일반 회의"

        # 0.1초 단위로 쪼개서 감시
        CHUNK = int(SAMPLE_RATE * 0.1)

        print("마이크 연결")
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            input_device_index=DEVICE_INDEX,
            frames_per_buffer=CHUNK
        )
        print("회의 기록 시작")

        audio_buffer = []  # 말할때 데이터 저장소
        silence_chunks = 0  # 침묵 카운터
        is_speaking = False  # 말하는중인지

        # 오디오 처리 루프
        while self.is_running:
            # 1. 오디오 데이터 읽기
            try:
                data = self.stream.read(CHUNK, exception_on_overflow=False)
                rms = self.get_rms(data)

                # 2. 소리가 임계값보다 크면 (말할때)
                if rms > SILENCE_THRESHOLD:
                    is_speaking = True
                    silence_chunks = 0
                    audio_buffer.append(data)
                    # print("소리가 커요")
                    # print(rms)

                # 3. 소리가 작으면 (침묵)
                else:
                    if is_speaking:
                        # 말하다가 조용해지면 버퍼에 일단 침묵도 조금 포함
                        audio_buffer.append(data)
                        silence_chunks += 1
                        # print("침묵중")
                        # print(silence_chunks)

                        # 침묵이 지속되면 문장 끝
                        if silence_chunks * 0.1 > SILENCE_DURATION:
                            is_speaking = False
                            # print("침묵 지속중")

                            # 너무 짧은 잡음 무시
                            if len(audio_buffer) * 0.1 >= MIN_AUDIO_LEN:
                                # 데이터 처리
                                full_audio_data = b''.join(audio_buffer)

                                # Whisper 입력용으로 변환 (int16 -> float32)
                                audio_np = np.frombuffer(full_audio_data, dtype=np.int16).astype(np.float32) / 32768.0

                                # Whisper 추론
                                asyncio.create_task(self.process_audio(audio_np))

                            # 버퍼 초기화
                            audio_buffer = []
                            silence_chunks = 0

                # 루프간 간격
                await asyncio.sleep(0.001)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"스트림 에러: {e}")
                continue

        # 종료 처리
        self._cleanup()

    # --------------------------------- 종료시 ----------------------------------------
    # 내부 초기화
    def _cleanup(self):
        print("\n종료 중...")
        self.is_running = False
        if hasattr(self, 'stream'):
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()
        self.save_report()

        # 리포트 저장용 함수
    def save_report(self):
        print("\n--------------------------------------------------")
        print("리포트 생성")
        print("--------------------------------------------------")

        if not os.path.exists(LOGS_DIR): os.makedirs(LOGS_DIR)

        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M')
        filename = f"meeting_report_{timestamp}.txt"
        path = os.path.join(LOGS_DIR, filename)

        with open(path, "w", encoding="utf-8") as f:
            f.write(f"회의 주제: {self.meeting_topic}\n")
            f.write(f"일시: {timestamp}\n")
            f.write("-" * 50 + "\n\n")

            f.write("[AI 요약 및 분석]\n")
            for log in self.analysis_logs:
                f.write(f"[{log['time']}]\n")
                f.write(f"- 요약: {log['summary']}\n")
                if log['decisions']: f.write(f"- 결정: {', '.join(log['decisions'])}\n")
                if log['todos']: f.write(f"- 할일: {', '.join(log['todos'])}\n")
                f.write(f"- 주제관련도: {log['off_topic_score']}/10\n\n")

            f.write("-" * 50 + "\n")
            f.write("[전체 대화 로그]\n")
            for line in self.full_transcript:
                f.write(f"{line}\n")

        print(f"저장 완료: {path}")

if __name__ == "__main__":
    assistant = MeetingAssistant()
    try:
        asyncio.run(assistant.start())
    except KeyboardInterrupt:
        assistant._cleanup()