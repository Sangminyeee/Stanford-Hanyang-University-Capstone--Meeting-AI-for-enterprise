# ver3에서 VAD, 비동기 적용 버전

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

# [AI 라이브러리]
from faster_whisper import WhisperModel
from sentence_transformers import SentenceTransformer, util
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from keybert import KeyBERT
from huggingface_hub import hf_hub_download, list_repo_files

# [화자 분리 라이브러리]
from pyannote.audio import Model
from pyannote.audio.core.inference import Inference
from scipy.spatial.distance import cdist

# [UI 라이브러리]
from tqdm import tqdm

# 토큰 불러오기
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")

# 설정값
DEVICE_INDEX = 1  # 장치 번호
SAMPLE_RATE = 16000
MAX_STRIKES = 2  # 이탈 허용 횟수
BUFFER_SIZE = 4  # 묶어서 요약할 문장 수
FLOW_THRESHOLD = 0.3  # 주제 유사도 임계값
WHISPER_MODEL_SIZE = "medium"  # Whisper 모델 크기 (small, medium, large-v3)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
MODELS_DIR = os.path.join(PARENT_DIR, "models") # 모델 저장 폴더
LOGS_DIR = os.path.join(PARENT_DIR, "log") # 로그 저장 폴더

# 침묵 감지
SILENCE_THRESHOLD = 500  # 최소 소리 (이거 넘어야 녹음됨)
SILENCE_DURATION = 0.3  # 몇초 이상 조용해야하는지
MIN_AUDIO_LEN = 1.0  # 최소 몇초 이상 말해야하는지

# CUDA 없으면 오류날 수 있음 주의!
DEVICE = "cuda"
COMPUTE_TYPE = "float16"


# 모델 다운로드하는 함수
def download_model_local(repo_id, local_dir, is_whisper=False):
    model_name = repo_id.split("/")[-1]
    print(f"\n 다운로드 체크: {model_name}")

    # Whisper 다운받을 때만 (모델 지정해줘야해서)
    if is_whisper:
        save_path = os.path.join(local_dir, f"faster-whisper-{model_name}")
        repo_id = f"Systran/faster-whisper-{model_name}"
    else:
        save_path = os.path.join(local_dir, model_name)

    # 로컬에 있는지 확인용
    if os.path.exists(save_path) and len(os.listdir(save_path)) > 0:
        print(f"\n모델 존재")
        return save_path

    # 폴더 파일 확인
    try:
        os.makedirs(save_path, exist_ok=True)
        files = list_repo_files(repo_id)
        target_files = [f for f in files if
                        f.endswith(".bin") or f.endswith(".json") or f.endswith(".txt") or f.endswith(
                            ".safetensors") or f.endswith(".yaml")]
    except Exception as e:
        print(f"[ERROR] 파일 목록 조회 실패: {e}")
        return save_path

    # 모델 다운로드
    for filename in tqdm(target_files, desc=f"다운로드 중: {model_name}", unit="file"):
        try:
            hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=save_path,
                local_dir_use_symlinks=False
            )
        except:
            pass
    return save_path


class MeetingAssistant:
    def __init__(self):
        # Whisper model 로드
        print("--------------------------------------------------")
        print("시작")
        print("환경:", DEVICE)
        print("--------------------------------------------------")

        # Whisper 모델
        print(f"STT 모델(Whisper {WHISPER_MODEL_SIZE}) 로드")
        try:
            model_path = download_model_local(WHISPER_MODEL_SIZE, MODELS_DIR, is_whisper=True)
            self.stt_model = WhisperModel(model_path, device=DEVICE, compute_type=COMPUTE_TYPE)
            print("Whisper 로드 완료")
        except Exception as e:
            print(f"Whisper 로드 실패: {e}")
            sys.exit(1)

        # 요약모델 로드
        print("요약 모델(T5) 로드")
        try:
            repo_id = "eenzeenee/t5-base-korean-summarization"
            model_path = download_model_local(repo_id, MODELS_DIR)
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.summarizer = AutoModelForSeq2SeqLM.from_pretrained(model_path).to(DEVICE)
            print("요약 모델(T5) 로드 완료")
        except Exception as e:
            print(f"요약 모델(T5) 로드 실패: {e}")
            sys.exit(1)

        # 판별모델 로드
        print("판별 모델(SBERT) 로드")
        try:
            repo_id = "kimseongsan/ko-sbert-384-reduced"
            model_path = download_model_local(repo_id, MODELS_DIR)
            self.sbert = SentenceTransformer(model_path)
            self.kw_model = KeyBERT(model=self.sbert)
            # self.todo_anchors = ["제가 하겠습니다.", "부탁드립니다.", "일정 잡읍시다."]
            # self.todo_embeddings = self.sbert.encode(self.todo_anchors, convert_to_tensor=True)
            print("판별 모델(SBERT) 로드 완료")
        except Exception as e:
            print(f"판별 모델(SBERT) 로드 실패: {e}")
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

        self.is_running = True
        self.transcript_buffer = []
        self.full_transcript = []
        self.section_summaries = []
        # self.todo_list = []
        self.meeting_topic = ""
        self.topic_embedding = None
        self.off_topic_strikes = 0

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

    # Sync 함수들 asyncio로 실행될것들
    # Whisper 추론함수
    def _run_whisper(self, audio_np):
        segments, _ = self.stt_model.transcribe(audio_np, beam_size=5, language="ko", condition_on_previous_text=False)
        return "".join([s.text + " " for s in segments]).strip()

    # 텍스트 요약 함수
    def _run_summarize(self, text):
        try:
            inputs = self.tokenizer("summarize: " + text, max_length=512, truncation=True, return_tensors="pt").to(
                DEVICE)
            output = self.summarizer.generate(**inputs, max_length=128, min_length=10, num_beams=4, length_penalty=2.0,
                                              early_stopping=True)
            return self.tokenizer.decode(output[0], skip_special_tokens=True)
        except:
            return text

    # 판별 모델 함수
    def _run_embedding(self, text):
        return self.sbert.encode(text, convert_to_tensor=True)

    # 화자 식별 함수
    def _run_speaker_id(self, audio_np):
        try:
            audio_tensor = torch.from_numpy(audio_np).float().unsqueeze(0).to(DEVICE)
            embedding_result = self.inference({"waveform": audio_tensor, "sample_rate": SAMPLE_RATE})

            if isinstance(embedding_result, torch.Tensor):
                new_emb = embedding_result.cpu().numpy()
            else:
                new_emb = embedding_result

            if not self.speaker_bank:
                self.speaker_bank[f"Speaker {self.speaker_counter}"] = new_emb
                self.speaker_counter += 1
                return f"Speaker {self.speaker_counter - 1}"

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
                self.speaker_bank[f"Speaker {self.speaker_counter}"] = new_emb
                self.speaker_counter += 1
                return f"Speaker {self.speaker_counter - 1}"
        except:
            return "Unknown"

    # Async 처리용
    # 요약, 분석 함수
    async def analyze_task(self, text_chunk):
        try:
            # 1. 요약
            summary = await asyncio.to_thread(self._run_summarize, text_chunk)
            now = datetime.datetime.now().strftime("%H:%M")
            self.section_summaries.append(f"[{now}] {summary}")
            print(f"\n[Summary] {summary}\n")

            # 2. 논점 체크
            if self.topic_embedding is not None:
                emb = await asyncio.to_thread(self._run_embedding, summary)
                score = util.cos_sim(self.topic_embedding, emb).item()
                if score < FLOW_THRESHOLD:
                    self.off_topic_strikes += 1
                    if self.off_topic_strikes >= MAX_STRIKES:
                        print(f"\n[Warning] 논점 이탈 감지 (유사도: {score:.2f})")
                else:
                    self.off_topic_strikes = 0
        except Exception as e:
            print(f"분석 에러: {e}")

    # 오디오 처리 파이프라인 (STT -> 화자 분리 -> 요약)
    async def process_audio(self, audio_np):
        try:
            # 1. Whisper 실행
            text_chunk = await asyncio.to_thread(self._run_whisper, audio_np)

            if text_chunk:
                # 2. 화자 식별
                speaker = await asyncio.to_thread(self._run_speaker_id, audio_np)

                log_text = f"[{speaker}] {text_chunk}"
                print(f"   {log_text}")

                self.full_transcript.append(log_text)
                self.transcript_buffer.append(text_chunk)

                # 3. 요약 조건 충족 시
                if len(self.transcript_buffer) >= BUFFER_SIZE:
                    full_text = " ".join(self.transcript_buffer)
                    self.transcript_buffer = []

                    # 4. 분석 작업을 백그라운드 태스크로 던짐 (await 안 함 -> 즉시 리턴)
                    asyncio.create_task(self.analyze_task(full_text))

        except Exception as e:
            print(f"처리 에러: {e}")

    # 리포트 저장용 함수
    def save_report(self):
        print("\n--------------------------------------------------")
        print("리포트 생성")
        print("--------------------------------------------------")

        full_text = " ".join(self.full_transcript)
        keywords = self.kw_model.extract_keywords(full_text, keyphrase_ngram_range=(1, 2), stop_words=None, top_n=5)

        report = []
        report.append(f"주제: {self.meeting_topic}\n")
        report.append("[키워드]")
        for kw, score in keywords: report.append(f"- {kw}")
        # report.append("\n[할 일]")
        # if self.todo_list:
        #     for t in self.todo_list: report.append(f"- {t}")
        # else:
        #     report.append("- 없음")
        report.append("\n[요약]")
        for s in self.section_summaries: report.append(f"- {s}")

        content = "\n".join(report)
        print(content)

        if not os.path.exists(LOGS_DIR): os.makedirs(LOGS_DIR)
        filename = f"meeting_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        path = os.path.join(LOGS_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n저장 완료: {path}")

    # 메인 시작 함수
    async def start(self):
        self.meeting_topic = input("회의 주제: ")
        self.topic_embedding = await asyncio.to_thread(self._run_embedding, self.meeting_topic)

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
            except Exception:
                continue

        # 종료 처리
        print("\n종료 중...")
        self.is_running = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()
        self.save_report()


if __name__ == "__main__":
    assistant = MeetingAssistant()
    try:
        asyncio.run(assistant.start())
    except KeyboardInterrupt:
        pass