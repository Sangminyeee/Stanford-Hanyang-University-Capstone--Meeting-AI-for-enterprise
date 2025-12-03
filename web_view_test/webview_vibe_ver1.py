import asyncio
import os
import sys
import datetime
import numpy as np
import pyaudio
import struct
import math
import torch
import queue
from dotenv import load_dotenv

# [AI 라이브러리]
from faster_whisper import WhisperModel
from sentence_transformers import SentenceTransformer, util
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from keybert import KeyBERT
from huggingface_hub import hf_hub_download, list_repo_files

# [화자 분리]
from pyannote.audio import Model
from pyannote.audio.core.inference import Inference
from scipy.spatial.distance import cdist

# [UI 라이브러리]
import streamlit as st
import streamlit.components.v1 as components

# [설정]
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")

# TF32 설정 (속도 향상)
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

# --- Streamlit 페이지 설정 ---
st.set_page_config(
    page_title="AI 회의 비서",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

SPEAKER_COLORS = [
    "#FF4B4B", # Red
    "#4CAF50", # Green
    "#2196F3", # Blue
    "#FFC107", # Amber
    "#9C27B0", # Purple
    "#00BCD4", # Cyan
    "#E91E63", # Pink
    "#CDDC39", # Lime
]

def get_speaker_color(speaker_name):
    """화자 이름에 따라 고정된 색상을 반환합니다."""
    if "Unknown" in speaker_name:
        return "#9E9E9E" # 회색
    try:
        # "Speaker 1" -> 1 추출 -> 색상 리스트 인덱스 계산
        idx = int(speaker_name.split()[-1]) - 1
        return SPEAKER_COLORS[idx % len(SPEAKER_COLORS)]
    except:
        return "#FAFAFA" # 기본 흰색
# 커스텀 CSS
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    .chat-bubble {
        padding: 12px;
        border-radius: 10px;
        margin-bottom: 10px;
        background-color: #262730;
    }
    .summary-item {
        padding: 12px;
        border-radius: 5px;
        margin-bottom: 10px;
        background-color: #1E1E1E;
        border-left: 4px solid #2196F3; /* 파란색 테두리 */
        font-size: 0.95em;
    }
    .speaker-label {
        font-weight: bold;
        color: #4CAF50;
        font-size: 0.8em;
    }

    .alert-box {
        background-color: #FF4B4B;
        color: white;
        padding: 10px;
        border-radius: 5px;
        font-weight: bold;
        text-align: center;
        animation: blink 2s infinite;
    }
    @keyframes blink { 50% { opacity: 0.5; } }
</style>
""", unsafe_allow_html=True)

# --- 설정값 ---
DEVICE_INDEX = 1
SAMPLE_RATE = 16000
BUFFER_SIZE = 4
FLOW_THRESHOLD = 0.35
WHISPER_MODEL_SIZE = "medium"

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
MODELS_DIR = os.path.join(PARENT_DIR, "models")
LOGS_DIR = os.path.join(PARENT_DIR, "log")

# VAD 설정 (이전 튜닝값 적용)
SILENCE_THRESHOLD = 500
SILENCE_DURATION = 0.3
MIN_AUDIO_LEN = 0.8

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"


# --------------------------------------------------------------------------------
# 모델 다운로드 및 로드
# --------------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def load_models():
    status = st.empty()
    status.info("⏳ AI 모델을 로딩 중입니다... (첫 실행 시 다운로드)")

    # 1. Whisper
    try:
        model_name = WHISPER_MODEL_SIZE
        repo_id = f"Systran/faster-whisper-{model_name}"
        save_path = os.path.join(MODELS_DIR, f"faster-whisper-{model_name}")

        if not os.path.exists(save_path) or len(os.listdir(save_path)) == 0:
            os.makedirs(save_path, exist_ok=True)
            files = list_repo_files(repo_id)
            target = [f for f in files if f.endswith((".bin", ".json", ".txt"))]
            for f in target: hf_hub_download(repo_id, f, local_dir=save_path)

        stt_model = WhisperModel(save_path, device=DEVICE, compute_type=COMPUTE_TYPE)
    except Exception as e:
        st.error(f"Whisper Error: {e}"); st.stop()

    # 2. T5
    try:
        repo_id = "eenzeenee/t5-base-korean-summarization"
        save_path = os.path.join(MODELS_DIR, "t5-base-korean-summarization")
        if not os.path.exists(save_path):
            os.makedirs(save_path, exist_ok=True)
            for f in list_repo_files(repo_id):
                if f.endswith((".bin", ".json", ".txt")): hf_hub_download(repo_id, f, local_dir=save_path)

        tokenizer = AutoTokenizer.from_pretrained(save_path)
        summarizer = AutoModelForSeq2SeqLM.from_pretrained(save_path).to(DEVICE)
    except:
        st.error("T5 Error"); st.stop()

    # 3. SBERT (논점 분석 및 키워드 추출용)
    try:
        repo_id = "kimseongsan/ko-sbert-384-reduced"
        save_path = os.path.join(MODELS_DIR, "ko-sbert-384-reduced")
        if not os.path.exists(save_path):
            os.makedirs(save_path, exist_ok=True)
            for f in list_repo_files(repo_id):
                if f.endswith((".bin", ".json", ".txt")): hf_hub_download(repo_id, f, local_dir=save_path)

        sbert = SentenceTransformer(save_path)
        kw_model = KeyBERT(model=sbert)
    except Exception as e:
        st.error(f"SBERT Error: {e}")
        print(e)
        st.stop()


    # 4. PyAnnote
    try:
        embedding_model = Model.from_pretrained("pyannote/wespeaker-voxceleb-resnet34-LM", use_auth_token=HF_TOKEN)
        inference = Inference(embedding_model, window="whole")
        inference.to(torch.device(DEVICE))
    except:
        st.error("PyAnnote Error (Token Check)"); st.stop()

    status.empty()
    return stt_model, tokenizer, summarizer, sbert, kw_model, inference


stt_model, tokenizer, summarizer, sbert, kw_model, inference = load_models()

# --------------------------------------------------------------------------------
# 세션 상태 초기화
# --------------------------------------------------------------------------------
if 'transcript' not in st.session_state: st.session_state.transcript = []
if 'summaries' not in st.session_state: st.session_state.summaries = []
if 'is_recording' not in st.session_state: st.session_state.is_recording = False
if 'topic' not in st.session_state: st.session_state.topic = ""
if 'topic_emb' not in st.session_state: st.session_state.topic_emb = None
if 'speaker_bank' not in st.session_state: st.session_state.speaker_bank = {}
if 'speaker_counter' not in st.session_state: st.session_state.speaker_counter = 1
if 'buffer' not in st.session_state: st.session_state.buffer = []


# --------------------------------------------------------------------------------
# 헬퍼 함수들
# --------------------------------------------------------------------------------
def get_rms(data):
    count = len(data) // 2
    shorts = struct.unpack("%dh" % count, data)
    sum_squares = sum(n * n for n in [s * (1.0 / 32768.0) for s in shorts])
    return math.sqrt(sum_squares / count) * 10000


def run_summarize(text):
    # 1. 입력 전처리: 너무 짧은 문장(단답형)은 요약 품질을 떨어뜨리므로 제거 가능
    # (여기서는 그대로 두되, T5에게 강제 명령을 내립니다)

    input_text = "summarize: " + text

    inputs = tokenizer(input_text, max_length=1024, truncation=True, return_tensors="pt").to(DEVICE)

    output = summarizer.generate(
        **inputs,
        max_length=150,  # 요약문 최대 길이
        min_length=20,  # 요약문 최소 길이 (너무 짧게 끝내지 마라)
        num_beams=5,  # 탐색 폭 확대 (더 좋은 문장 찾기)
        early_stopping=True,

        # [핵심 수정 1] 반복 방지 (같은 단어 구절이 3번 이상 나오면 차단)
        no_repeat_ngram_size=3,

        # [핵심 수정 2] 패널티 부여 (원문에 있는 단어를 그대로 쓰면 감점 -> 바꿔 말하기 유도)
        repetition_penalty=1.5,

        # [핵심 수정 3] 길이 패널티 (짧을수록 점수를 깎음 -> 좀 더 길고 자세하게 써라)
        length_penalty=1.2
    )

    summary = tokenizer.decode(output[0], skip_special_tokens=True)

    # 만약 결과가 원문과 너무 똑같으면 (길이 차이가 별로 없으면) 실패로 간주
    if len(summary) > len(text) * 0.8:
        return f"👉 {summary}"  # 그대로 출력하되 아이콘 붙임

    return summary


# [수정됨] 화자 식별 (Session State 직접 접근 안 함)
def identify_speaker(audio_np, speaker_bank, speaker_counter):
    try:
        if len(audio_np) / SAMPLE_RATE < 1.0:
            return "Unknown", speaker_bank, speaker_counter

        audio_tensor = torch.from_numpy(audio_np).float().unsqueeze(0).to(DEVICE)
        embedding_result = inference({"waveform": audio_tensor, "sample_rate": SAMPLE_RATE})

        if isinstance(embedding_result, torch.Tensor):
            new_emb = embedding_result.cpu().numpy()
        else:
            new_emb = embedding_result

        if not speaker_bank:
            name = f"Speaker {speaker_counter}"
            speaker_bank[name] = new_emb
            return name, speaker_bank, speaker_counter + 1

        min_dist = 100.0
        best_match = None

        for name, saved_emb in speaker_bank.items():
            dist = cdist(new_emb.reshape(1, -1), saved_emb.reshape(1, -1), metric="cosine")[0][0]
            if dist < min_dist:
                min_dist = dist
                best_match = name

        if min_dist < 0.7:  # 임계값 0.7
            return best_match, speaker_bank, speaker_counter
        else:
            new_name = f"Speaker {speaker_counter}"
            speaker_bank[new_name] = new_emb
            return new_name, speaker_bank, speaker_counter + 1

    except Exception:
        return "Unknown", speaker_bank, speaker_counter

def render_chat_bubble(speaker, text):
    color = get_speaker_color(speaker)
    st.markdown(f"""
    <div class='chat-bubble' style='border-left: 5px solid {color};'>
        <div class='speaker-label' style='color: {color};'>{speaker}</div>
        {text}
    </div>
    """, unsafe_allow_html=True)

def render_summary(text):
    st.markdown(f"""
    <div class='summary-item'>
        📌 {text}
    </div>
    """, unsafe_allow_html=True)

def auto_scroll():
    js = """
    <script>
        // 1. 채팅 스크롤
        var chats = window.parent.document.querySelectorAll('.chat-bubble');
        if (chats.length > 0) {
            chats[chats.length - 1].scrollIntoView({behavior: "smooth", block: "end", inline: "nearest"});
        }
        // 2. 요약 스크롤 (summary-item 클래스 대상)
        var summaries = window.parent.document.querySelectorAll('.summary-item');
        if (summaries.length > 0) {
            summaries[summaries.length - 1].scrollIntoView({behavior: "smooth", block: "end", inline: "nearest"});
        }
    </script>
    """
    components.html(js, height=0)

# --------------------------------------------------------------------------------
# UI 구성
# --------------------------------------------------------------------------------
st.title("🎙️ AI 회의 비서 Dashboard")

with st.sidebar:
    st.header("설정 및 제어")
    topic_input = st.text_input("회의 주제 입력", placeholder="예: 3분기 마케팅 전략")

    col1, col2 = st.columns(2)
    with col1:
        start_btn = st.button("▶ 시작", type="primary", use_container_width=True)
    with col2:
        stop_btn = st.button("⏹ 종료", use_container_width=True)

    st.divider()
    st.markdown("### 📊 실시간 현황")
    status_indicator = st.empty()

    st.divider()
    if st.button("💾 리포트 저장"):
        if not os.path.exists(LOGS_DIR): os.makedirs(LOGS_DIR)
        filename = f"meeting_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        path = os.path.join(LOGS_DIR, filename)

        full_text = " ".join([f"[{t['speaker']}] {t['text']}" for t in st.session_state.transcript])

        # 키워드 추출 (KeyBERT 사용)
        try:
            keywords = kw_model.extract_keywords(full_text, keyphrase_ngram_range=(1, 2), stop_words=None, top_n=5)
            kw_text = "\n".join([f"- {kw[0]}" for kw in keywords])
        except:
            kw_text = "키워드 없음"

        content = f"주제: {st.session_state.topic}\n\n[주요 키워드]\n{kw_text}\n\n[요약]\n" + "\n".join(
            st.session_state.summaries) + f"\n\n[전체 대화]\n{full_text}"

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        st.success(f"저장 완료: {filename}")

# 메인 레이아웃
col_transcript, col_analysis = st.columns([3, 2])

with col_transcript:
    st.subheader("실시간 대화 내용")
    transcript_container = st.container(height=600, border=True)

with col_analysis:
    st.subheader("AI 분석 & 요약")

    st.markdown("**⚠️ 논점 이탈 경고**")
    alert_box = st.empty()

    st.markdown("**📝 실시간 요약**")
    summary_container = st.container(height=400, border=True)


# --------------------------------------------------------------------------------
# 메인 로직
# --------------------------------------------------------------------------------
async def main_loop():
    p = pyaudio.PyAudio()
    CHUNK = int(SAMPLE_RATE * 0.1)

    try:
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE, input=True,
                        input_device_index=DEVICE_INDEX, frames_per_buffer=CHUNK)
    except:
        st.sidebar.error("마이크 연결 실패! 장치 번호를 확인하세요.")
        return

    status_indicator.info("녹음 중... (말씀하세요)")

    audio_buffer = []
    silence_chunks = 0
    is_speaking = False

    if st.session_state.topic and st.session_state.topic_emb is None:
        st.session_state.topic_emb = await asyncio.to_thread(sbert.encode, st.session_state.topic,
                                                             convert_to_tensor=True)

    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True

    while st.session_state.is_recording:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            rms = get_rms(data)
        except:
            continue

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

                        segments, _ = await asyncio.to_thread(stt_model.transcribe, audio_np, beam_size=5,
                                                              language="ko", condition_on_previous_text=False)
                        text = "".join([s.text + " " for s in segments]).strip()
                        last_text = st.session_state.transcript[-1]['text'] if st.session_state.transcript else ""

                        if text and text != last_text:
                            # 비동기때문에 인자로 전달해야하ㅣㅁ 여기
                            current_bank = st.session_state.speaker_bank.copy()
                            current_cnt = st.session_state.speaker_counter

                            speaker, new_bank, new_cnt = await asyncio.to_thread(
                                identify_speaker, audio_np, current_bank, current_cnt
                            )

                            st.session_state.speaker_bank = new_bank
                            st.session_state.speaker_counter = new_cnt

                            # 4. 데이터 저장
                            st.session_state.transcript.append({"speaker": speaker, "text": text})
                            st.session_state.buffer.append(text)

                            with transcript_container:
                                render_chat_bubble(speaker, text)
                                auto_scroll()

                            # 요약 및 분석
                            if len(st.session_state.buffer) >= BUFFER_SIZE:
                                full_text = " ".join(st.session_state.buffer)
                                st.session_state.buffer = []  # 버퍼 비우기

                                # 요약
                                summary = await asyncio.to_thread(run_summarize, full_text)
                                st.session_state.summaries.append(summary)
                                with summary_container:
                                    st.markdown(f"• {summary}")

                                # 논점 분석
                                if st.session_state.topic_emb is not None:
                                    sum_emb = await asyncio.to_thread(sbert.encode, summary, convert_to_tensor=True)
                                    sim = util.cos_sim(st.session_state.topic_emb, sum_emb).item()

                                    if sim < FLOW_THRESHOLD:
                                        alert_box.markdown(f"<div class='alert-box'>🚨 논점 이탈 감지 (유사도: {sim:.2f})</div>",
                                                           unsafe_allow_html=True)
                                    else:
                                        alert_box.empty()

                    audio_buffer = []
                    silence_chunks = 0

        await asyncio.sleep(0.01)

    stream.stop_stream()
    stream.close()
    p.terminate()
    status_indicator.warning("녹음이 종료되었습니다.")


# --------------------------------------------------------------------------------
# 버튼 핸들러
# --------------------------------------------------------------------------------
if start_btn:
    st.session_state.is_recording = True
    st.session_state.topic = topic_input
    st.session_state.transcript = []
    st.session_state.summaries = []
    st.session_state.speaker_bank = {}  # 초기화
    st.session_state.speaker_counter = 1
    st.rerun()

if stop_btn:
    st.session_state.is_recording = False
    st.rerun()

if st.session_state.is_recording:
    asyncio.run(main_loop())
else:
    with transcript_container:
        for chat in st.session_state.transcript:
            render_chat_bubble(chat['speaker'], chat['text'])
            auto_scroll()

    with summary_container:
        for s in st.session_state.summaries:
            render_summary(s)