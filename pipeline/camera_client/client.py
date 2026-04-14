"""
IGNITER Camera Client

Captures webcam frames, runs eye tracking + emotion detection, and
streams results to the backend via WebSocket.

Usage:
    python client.py <SESSION_ID>

    SESSION_ID is printed on the viewer page after registration.
    Keep this window open while the participant explores the 360° view.
"""
import asyncio
import json
import os
import sys
import time

import cv2

# ── path setup so we can reuse existing SIH_MVP modules ─────────────────────
_HERE        = os.path.dirname(os.path.abspath(__file__))
_SRC         = os.path.join(_HERE, "..", "..", "SIH_MVP", "src")
_MODELS      = os.path.join(_HERE, "..", "..", "SIH_MVP", "models")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from emotion_detector import EmotionDetector
from eye_tracking import EyeTracker

BACKEND_WS   = os.environ.get("BACKEND_WS", "ws://127.0.0.1:8000/ws/camera")
MODEL_PATH   = os.path.join(_MODELS, "best_emotion_model.h5")
SEND_FPS     = 10          # frames per second sent to backend
FRAME_DELAY  = 1.0 / SEND_FPS


async def stream(session_id: str):
    # import here so the module is still importable without aiohttp installed
    import aiohttp

    uri = f"{BACKEND_WS}?session_id={session_id}"
    print(f"Connecting to {uri}")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: cannot open webcam")
        return

    et = EyeTracker()
    ed = EmotionDetector(model_path=MODEL_PATH)

    timeout = aiohttp.ClientTimeout(total=None, connect=10)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        try:
            async with http.ws_connect(uri) as ws:
                print(f"Connected — streaming at {SEND_FPS} fps. Press ESC in camera window to stop.")
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        print("Camera read failed — stopping")
                        break

                    h, w = frame.shape[:2]
                    info = et.process_frame(frame)

                    # ── emotion from face crop ──────────────────────────────
                    emotion_label = "unknown"
                    emotion_conf  = 0.0
                    if info["landmarks"]:
                        lm  = info["landmarks"]
                        xs  = [int(p.x * w) for p in lm]
                        ys  = [int(p.y * h) for p in lm]
                        x1  = max(0, min(xs) - 20)
                        y1  = max(0, min(ys) - 20)
                        x2  = min(w, max(xs) + 20)
                        y2  = min(h, max(ys) + 20)
                        crop = frame[y1:y2, x1:x2]
                        if crop.size > 100:
                            try:
                                res           = ed.predict_from_face(crop)
                                emotion_label = res["label"]
                                emotion_conf  = res["confidence"]
                            except Exception:
                                pass

                    gaze_dir = info.get("gaze_direction", "center")
                    ear_l    = info.get("left_ear")
                    ear_r    = info.get("right_ear")

                    payload = {
                        "timestamp":     time.time(),
                        "emotion":       emotion_label,
                        "confidence":    round(emotion_conf, 3),
                        "gaze_direction": gaze_dir,
                        "ear_left":      round(ear_l, 4) if ear_l is not None else None,
                        "ear_right":     round(ear_r, 4) if ear_r is not None else None,
                    }
                    await ws.send_str(json.dumps(payload))

                    # ── local display ───────────────────────────────────────
                    disp = info.get("frame", frame)
                    color = (0, 255, 0) if gaze_dir == "center" else (0, 0, 255)
                    cv2.putText(disp, f"Gaze: {gaze_dir}",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                    cv2.putText(disp, f"Emotion: {emotion_label} ({emotion_conf:.2f})",
                                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 180, 0), 2)
                    cv2.putText(disp, f"Session: {session_id}",
                                (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
                    cv2.imshow("IGNITER — Camera Client (ESC to stop)", disp)

                    if cv2.waitKey(1) & 0xFF == 27:
                        print("ESC pressed — stopping camera client")
                        break

                    await asyncio.sleep(FRAME_DELAY)

        except aiohttp.ClientConnectorError:
            print(f"Cannot connect to backend at {uri}")
            print("Make sure the backend is running: python backend/app.py")

    cap.release()
    cv2.destroyAllWindows()
    print("Camera client stopped.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python client.py <SESSION_ID>")
        print("  SESSION_ID is shown on the viewer page after you register.")
        sys.exit(1)
    asyncio.run(stream(sys.argv[1].upper()))
