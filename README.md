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
