# IGNITER
### Multimodal EV Interior Experience Research Platform
**Smart India Hackathon 2025 — Problem Statement #25221**

> *VR + Eye-Tracking Solution to Capture Customer Reactions for EV Product Design*

Instead of VR, IGNITER uses a **360° EV interior image** with color-mask hotspot mapping, validated by real-time eye tracking, emotion detection, and physiological sensors — combining all streams into a per-session AI report and targeted survey for EV designers.

---

## What It Does

A participant sits in front of a screen and explores a 360° EV interior by dragging around. While they explore:

- **Hotspot Gaze Tracking** — the 360° viewer detects which interior area (Steering Wheel, Infotainment, Seats, etc.) the viewport is centred on, every 200ms
- **Eye Tracking** — a webcam runs MediaPipe to confirm whether the user is actually looking at the screen (`center / left / right`) and detects blinks
- **Emotion Detection** — a TensorFlow model classifies the user's facial expression (Happy, Sad, Angry, Neutral, etc.) in real time
- **Physiological Sensors** — an ESP32 microcontroller reads GSR (galvanic skin response) and BPM, which are used to compute a physiological stress score
- **Data Fusion** — all four streams are merged per session, correlating which emotion and stress level the user had while looking at each part of the car
- **AI Report** — auto-generated insights, dwell-time charts, emotion distribution, stress timeline
- **Targeted Survey** — questions are dynamically generated based on which areas the user looked at most

---

## System Architecture

```
Browser (register.html)
        │
        │  POST /api/session/start
        ▼
┌─────────────────────────────────────────────┐
│         Unified aiohttp Backend             │
│         pipeline/backend/app.py             │
│                                             │
│  REST:  /api/session/{id}/end               │
│         /api/session/{id}/summary           │
│         /api/session/{id}/survey            │
│                                             │
│  WS:    /ws/gaze   ← browser viewer         │
│         /ws/camera ← camera client          │
│  Poll:  ESP32 HTTP /data every 1s           │
└──────────┬──────────────┬───────────────────┘
           │              │
    ┌──────┘        ┌─────┘
    ▼               ▼
viewer.html     camera_client/client.py
360° panorama   Webcam → EyeTracker
+ mask hotspot  + EmotionDetector
tracking        → WS /ws/camera
→ WS /ws/gaze
           │
           ▼
    Data Fusion (fusion.py)
           │
           ▼
    survey.html → report.html
```

---

## Project Structure

```
IGNITER/
│
├── pipeline/                        # Main unified pipeline (START HERE)
│   ├── backend/
│   │   ├── app.py                   # aiohttp server — all routes + WS + ESP32 poller
│   │   ├── session.py               # Session store + data models
│   │   ├── fusion.py                # Data fusion engine + insight generation
│   │   └── requirements.txt
│   │
│   ├── camera_client/
│   │   └── client.py                # Webcam → eye tracking + emotion → backend WS
│   │
│   └── frontend/
│       ├── register.html            # Participant registration form
│       ├── viewer.html              # 360° explorer + live gaze overlay
│       ├── survey.html              # AI-targeted survey
│       └── report.html              # Full experience report + charts
│
├── CAR-INTERIOR/
│   ├── car3.jpg                     # 360° equirectangular EV interior image
│   ├── mask.png                     # Color-coded hotspot mask
│   ├── index2.html                  # Standalone 360° viewer (for reference)
│   └── code.py                      # Simple static file server
│
├── sensor/
│   └── sensor/
│       ├── run.py                   # Standalone aiohttp sensor dashboard
│       ├── sensors/
│       │   ├── esp32_poller.py      # Async ESP32 HTTP poller
│       │   ├── esp32_reader.py      # Raw JSON → typed sample
│       │   ├── sensor_manager.py    # Physiology-based stress fusion
│       │   └── stress_predictor.py  # Rule-based stress predictor
│       ├── config/settings.py
│       └── static/index.html        # Live sensor dashboard (standalone)
│
└── ESP32_c3/
    └── ESP32_c3.ino                 # Arduino firmware — WiFi HTTP server (BPM + GSR)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, aiohttp, asyncio |
| Eye Tracking | MediaPipe FaceLandmarker (Tasks API) |
| Emotion Detection | TensorFlow / Keras |
| 360° Viewer | Pannellum.js + color-mask pixel lookup |
| Physiological Sensors | ESP32-C3, GSR sensor, pulse sensor |
| Frontend | Vanilla HTML / CSS / JavaScript, Chart.js |
| Hardware Firmware | Arduino C++ (ESP32 WiFi HTTP server) |

---

## Requirements

### Python packages

```bash
pip install aiohttp opencv-python mediapipe tensorflow
```

| Package | Used for |
|---|---|
| `aiohttp` | Backend server + WebSocket + ESP32 polling |
| `opencv-python` | Webcam capture, frame processing |
| `mediapipe` | Face landmark detection, iris tracking |
| `tensorflow` | Emotion classification model |

> **Note:** Requires `mediapipe >= 0.10.30`. The face landmark model (`face_landmarker.task`, ~35 MB) is downloaded automatically on first run.

### Hardware (optional)
- ESP32-C3 microcontroller
- GSR (galvanic skin response) sensor on ADC pin 1
- Pulse / BPM sensor

---

## Steps to Run

### Step 1 — Flash the ESP32 *(skip if no hardware)*

1. Open `ESP32_c3/ESP32_c3.ino` in Arduino IDE
2. Set your WiFi credentials on lines 4–5:
   ```cpp
   const char* ssid     = "YOUR_WIFI_NAME";
   const char* password = "YOUR_WIFI_PASSWORD";
   ```
3. Upload to the ESP32-C3
4. Open Serial Monitor (115200 baud) → note the IP address printed
5. Set the IP in the backend (see Step 2)

---

### Step 2 — Configure ESP32 IP

Open `pipeline/backend/app.py` and find:
```python
esp_ip = os.environ.get("ESP32_IP", "10.60.60.160")
```
Replace `10.60.60.160` with your ESP32's IP, **or** set it as an environment variable:
```bash
# Windows
set ESP32_IP=192.168.x.x

# Linux / Mac
export ESP32_IP=192.168.x.x
```

---

### Step 3 — Install dependencies

```bash
pip install aiohttp opencv-python mediapipe tensorflow
```

---

### Step 4 — Start the backend

```bash
cd pipeline/backend
python app.py
```

Expected output:
```
Starting IGNITER pipeline on http://0.0.0.0:8000
[ESP32] poller → http://10.60.60.160/data
```

---

### Step 5 — Open the registration page

Go to:
```
http://localhost:8000
```

Fill in the participant's details (name, age, EV experience, etc.) and click **Begin Experience**.

---

### Step 6 — Start the camera client

After registration, the viewer page shows a modal with the exact command. Copy it and run it in a **second terminal**:

```bash
cd IGNITER
python pipeline/camera_client/client.py <SESSION_ID>
```

Replace `<SESSION_ID>` with the 8-character ID shown on the viewer page (e.g. `A1B2C3D4`).

> **First run:** MediaPipe will automatically download `face_landmarker.task` (~35 MB). This happens once.

A webcam window opens showing live eye tracking and emotion. The viewer page's **Camera** badge turns green when connected.

---

### Step 7 — Run the session

- The participant **drags to explore** the 360° EV interior
- A **3-minute timer** counts down
- The top HUD shows: current hotspot, detected emotion, gaze direction, camera validation status
- The right panel shows a live ranked dwell-time list per area
- Click **End Session** anytime, or let the timer expire

---

### Step 8 — Complete the survey

The browser auto-redirects to the **survey page**:
- Shows the top areas the participant looked at most
- Asks targeted questions specific to those areas
- General rating questions at the end

Submit → auto-redirects to the report.

---

### Step 9 — View the report

The **report page** shows:
- Key metrics (top focus area, dominant emotion, avg stress, distraction rate)
- AI-generated insights
- Dwell time bar chart per area
- Emotion distribution pie chart
- Stress-over-time graph *(if ESP32 connected)*
- Per-area breakdown table (raw dwell, validated dwell, dominant emotion, correlated stress)
- Survey responses

Click **Print / Save PDF** to export.

---

## Running Without Hardware

Both the ESP32 and camera are optional — the system degrades gracefully:

| Component missing | Effect |
|---|---|
| ESP32 | Stress data shows N/A in report |
| Camera client | All gaze ticks marked as validated, emotion shows `unknown` |
| Both | Only 360° hotspot dwell data is recorded — still produces a report |

---

## Hotspot Color Map

The `mask.png` file maps colors to interior areas:

| Color | Area |
|---|---|
| `#ff0000` | Steering Wheel |
| `#ffff00` | Instrument Cluster |
| `#00ff00` | Infotainment Screen |
| `#0000ff` | AC Controls |
| `#00ffff` | Gear Selector |
| `#ff00ff` | Handrest / Center Console |
| `#ff7f00` | Accelerator / Brake |
| `#8000ff` | Driver Door |
| `#7fff00` | Windshield |
| `#00bfff` | Passenger Dashboard |
| `#ff1493` | Passenger Door |
| `#008080` | Passenger Seat |
| `#ff6347` | Driver Seat |
| `#ffd700` | Sun Visor |
| `#7fffd4` | Rear View Mirror |
| `#adff2f` | Back Seat |
| `#9400d3` | Sunroof |

---

## Team

Built for **Smart India Hackathon 2024** — Problem Statement #25221
*VR + Eye-Tracking Solution to Capture Customer Reactions for EV Product Design*
