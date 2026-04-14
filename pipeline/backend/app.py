"""
IGNITER Pipeline — Unified aiohttp backend.

Serves all HTML pages, handles REST session lifecycle, and manages three
WebSocket streams (browser gaze events, camera client, ESP32 sensor).
All three streams are written into the active Session in real-time and
fused at session end.

Run:
    cd pipeline/backend
    python app.py
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import aiohttp
from aiohttp import WSMsgType, web

# ── path setup ──────────────────────────────────────────────────────────────
BACKEND_DIR  = Path(__file__).parent
PIPELINE_DIR = BACKEND_DIR.parent
PROJECT_DIR  = PIPELINE_DIR.parent
FRONTEND_DIR = PIPELINE_DIR / "frontend"
SENSOR_PKG   = PROJECT_DIR / "sensor" / "sensor"

if str(SENSOR_PKG) not in sys.path:
    sys.path.insert(0, str(SENSOR_PKG))

from fusion import fuse
from session import CameraFrame, GazeEvent, SensorSample, SessionStore

store = SessionStore()

# Active WebSocket connections keyed by session_id
_gaze_ws:   dict[str, web.WebSocketResponse] = {}
_camera_ws: dict[str, web.WebSocketResponse] = {}


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

async def page_register(request):
    return web.FileResponse(FRONTEND_DIR / "register.html")

async def page_viewer(request):
    return web.FileResponse(FRONTEND_DIR / "viewer.html")

async def page_survey(request):
    return web.FileResponse(FRONTEND_DIR / "survey.html")

async def page_report(request):
    return web.FileResponse(FRONTEND_DIR / "report.html")


# ═══════════════════════════════════════════════════════════════════════════════
#  REST API
# ═══════════════════════════════════════════════════════════════════════════════

async def api_session_start(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)

    if not data.get("name") or not data.get("age"):
        return web.json_response({"error": "'name' and 'age' are required"}, status=400)

    session = store.create(data)
    print(f"[session] started {session.session_id} — {data.get('name')}")
    return web.json_response({"session_id": session.session_id})


async def api_session_end(request):
    sid = request.match_info["sid"]
    session = store.end(sid)
    if not session:
        return web.json_response({"error": "session not found"}, status=404)

    result = fuse(session)
    session.fusion_result = result
    print(f"[session] ended {sid} — duration {session.duration}s, "
          f"{len(session.gaze_events)} gaze events, "
          f"{len(session.camera_frames)} camera frames, "
          f"{len(session.sensor_samples)} sensor samples")
    return web.json_response(result)


async def api_summary(request):
    sid = request.match_info["sid"]
    session = store.get(sid)
    if not session:
        return web.json_response({"error": "session not found"}, status=404)
    # return cached result if already fused, otherwise compute on-the-fly
    return web.json_response(session.fusion_result or fuse(session))


async def api_survey_submit(request):
    sid = request.match_info["sid"]
    session = store.get(sid)
    if not session:
        return web.json_response({"error": "session not found"}, status=404)
    try:
        session.survey_responses = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)
    print(f"[session] survey received for {sid}")
    return web.json_response({"ok": True})


# ═══════════════════════════════════════════════════════════════════════════════
#  WEBSOCKET — Browser gaze events
# ═══════════════════════════════════════════════════════════════════════════════

async def ws_gaze(request):
    sid = request.rel_url.query.get("session_id", "").upper()
    session = store.get(sid)
    if not session:
        return web.Response(status=400, text="invalid or unknown session_id")

    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    _gaze_ws[sid] = ws
    print(f"[gaze WS] connected — session {sid}")

    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            try:
                d = json.loads(msg.data)
                if d.get("type") == "gaze" and d.get("part"):
                    session.gaze_events.append(GazeEvent(
                        timestamp = d.get("timestamp", time.time()),
                        part      = d["part"],
                        validated = d.get("validated", True),
                        emotion   = d.get("emotion", "unknown"),
                        ear_avg   = float(d.get("ear_avg", 0.0)),
                    ))
            except Exception as e:
                print(f"[gaze WS] parse error: {e}")
        elif msg.type == WSMsgType.ERROR:
            print(f"[gaze WS] error: {ws.exception()}")

    _gaze_ws.pop(sid, None)
    print(f"[gaze WS] disconnected — session {sid}")
    return ws


# ═══════════════════════════════════════════════════════════════════════════════
#  WEBSOCKET — Camera client (eye tracking + emotion)
# ═══════════════════════════════════════════════════════════════════════════════

async def ws_camera(request):
    sid = request.rel_url.query.get("session_id", "").upper()
    session = store.get(sid)
    if not session:
        return web.Response(status=400, text="invalid or unknown session_id")

    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    _camera_ws[sid] = ws
    print(f"[camera WS] connected — session {sid}")

    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            try:
                d = json.loads(msg.data)
                session.camera_frames.append(CameraFrame(
                    timestamp           = d.get("timestamp", time.time()),
                    emotion             = d.get("emotion", "unknown"),
                    emotion_confidence  = float(d.get("confidence", 0.0)),
                    gaze_direction      = d.get("gaze_direction", "center"),
                    ear_left            = float(d.get("ear_left") or 0.0),
                    ear_right           = float(d.get("ear_right") or 0.0),
                ))
                # push live camera state back to the viewer for validation overlay
                gaze_ws = _gaze_ws.get(sid)
                if gaze_ws and not gaze_ws.closed:
                    await gaze_ws.send_str(json.dumps({
                        "type":           "camera_update",
                        "emotion":        d.get("emotion", "unknown"),
                        "gaze_direction": d.get("gaze_direction", "center"),
                        "ear_avg":        ((float(d.get("ear_left") or 0) +
                                           float(d.get("ear_right") or 0)) / 2),
                    }))
            except Exception as e:
                print(f"[camera WS] parse error: {e}")
        elif msg.type == WSMsgType.ERROR:
            print(f"[camera WS] error: {ws.exception()}")

    _camera_ws.pop(sid, None)
    print(f"[camera WS] disconnected — session {sid}")
    return ws


# ═══════════════════════════════════════════════════════════════════════════════
#  ESP32 background poller
# ═══════════════════════════════════════════════════════════════════════════════

async def _esp32_poll_loop(app):
    esp_ip       = os.environ.get("ESP32_IP", "10.60.60.160")
    poll_interval = float(os.environ.get("ESP32_POLL_INTERVAL", "1.0"))
    url           = f"http://{esp_ip}/data"
    print(f"[ESP32] poller → {url}")

    try:
        from sensors.sensor_manager   import SensorManager
        from sensors.stress_predictor import ESP32StressPredictor
        manager   = SensorManager()
        predictor = ESP32StressPredictor()
    except ImportError as e:
        print(f"[ESP32] sensor modules not found ({e}), poller disabled")
        return

    timeout = aiohttp.ClientTimeout(total=5)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        while True:
            try:
                async with http.get(url) as resp:
                    if resp.status == 200:
                        raw       = await resp.json(content_type=None)
                        fused_s   = manager.ingest(raw)   or {}
                        predicted = predictor.predict(raw) or {}
                        payload   = {**fused_s, **predicted, "timestamp": time.time()}
                        app["esp32_last"] = payload

                        sample = SensorSample(
                            timestamp   = payload["timestamp"],
                            bpm         = float(payload.get("bpm", 0)),
                            gsr         = float(payload.get("gsr", 0)),
                            stress      = float(payload.get("stress", 0)),
                            ml_stress   = float(payload.get("ml_stress", 0)),
                            stress_level= payload.get("stress_level", "unknown"),
                        )
                        # attach to all running sessions
                        for sess in store.active_sessions():
                            sess.sensor_samples.append(sample)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[ESP32] poll error: {e}")

            await asyncio.sleep(poll_interval)


async def _start_esp32_poller(app):
    app["esp32_task"] = asyncio.get_event_loop().create_task(_esp32_poll_loop(app))


async def _cleanup(app):
    task = app.get("esp32_task")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    for ws in list(_gaze_ws.values()) + list(_camera_ws.values()):
        if not ws.closed:
            await ws.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  APP FACTORY
# ═══════════════════════════════════════════════════════════════════════════════

def create_app() -> web.Application:
    app = web.Application()

    # ── pages ──
    app.router.add_get("/",        page_register)
    app.router.add_get("/viewer",  page_viewer)
    app.router.add_get("/survey",  page_survey)
    app.router.add_get("/report",  page_report)

    # ── static assets from CAR-INTERIOR (car3.jpg, mask.png) ──
    car_interior = PROJECT_DIR / "CAR-INTERIOR"
    if car_interior.exists():
        app.router.add_static("/assets/", path=str(car_interior), name="assets")
    else:
        print(f"[warn] CAR-INTERIOR not found at {car_interior}")

    # ── REST ──
    app.router.add_post("/api/session/start",          api_session_start)
    app.router.add_post("/api/session/{sid}/end",      api_session_end)
    app.router.add_get ("/api/session/{sid}/summary",  api_summary)
    app.router.add_post("/api/session/{sid}/survey",   api_survey_submit)

    # ── WebSockets ──
    app.router.add_get("/ws/gaze",   ws_gaze)
    app.router.add_get("/ws/camera", ws_camera)

    app.on_startup.append(_start_esp32_poller)
    app.on_cleanup.append(_cleanup)

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting IGNITER pipeline on http://0.0.0.0:{port}")
    web.run_app(create_app(), host="0.0.0.0", port=port)
