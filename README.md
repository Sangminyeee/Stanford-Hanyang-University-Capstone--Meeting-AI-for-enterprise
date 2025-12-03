<div align="center">

# 🎓 Stanford University Capstone  
## **Enterprise AI Meeting Facilitation System**

### _AI-powered platform for real-time meeting analysis, cognitive load monitoring, and enhanced communication efficiency._

</div>

---

## ✨ Overview

This project develops an **enterprise-grade AI meeting facilitation system** that analyzes:

- 🗣 **Speaking patterns & participation balance**  
- 🧠 **Cognitive load signals**  
- 🧵 **Topic flow & drift detection**  
- 📊 **Post-meeting analytics**

The system integrates three major layers:

1. **Hardware Layer** – Edge device, sensors, audio capture  
2. **AI Layer** – STT, diarization, topic modeling, metric extraction  
3. **Web Layer** – Real-time feedback dashboard + analytics interface  

Documentation contains architectural design, planning logs, and research notes.

---

## 📁 Project Structure

```plaintext
/src
   /hardware
        - Edge device & audio preprocessing
        - Sensor integration
        - Microcontroller (e.g., Raspberry Pi, Arduino) code

   /web
        - Live meeting feedback UI
        - Analytics dashboard
        - Backend API integration

   /ai
        - Whisper / Deepgram STT pipeline
        - Speaker diarization
        - Topic drift detection
        - Meeting metrics & AI models

/docs
   - System architecture diagrams
   - UX/UI design & wireframes
   - Research notes & literature review
   - Meeting logs & planning documents

/tests
   - Unit tests
   - Integration tests
   - Experimental scripts
```

## AI readme temp
### 사전 준비
프로젝트 폴더에 .env 파일 생성

### 화자분리용
화자분리용 pyannote 사용하려면 이게 선행되어야함
1. 허깅페이스 가입
2. 모델 사용 동의
   - https://huggingface.co/pyannote/segmentation-3.0
   - https://huggingface.co/pyannote/speaker-diarization-3.1
3. read 권한으로 access 토큰 발급
4. .env 파일에 HF_TOKEN =  작성하고 위 발급받은 토큰 붙여넣기


### 의존성 설치
```uv pip install -r requirements.txt --index-url https://pypi.org/simple```

or

```pip install -r requirements.txt```

### 참고사항
지금 보면 말이 너무 이어지거나 요약, 화자분리가 제대로 잘 안되는거 볼수있는데
나중에 모델 바꿀거기도 하고 아직 하이퍼파라미터 최적화를 못시켜서
추후에 진행해야겠다

### 웹뷰용
```streamlit run web_view_test/webview_vibe_ver1.py```
