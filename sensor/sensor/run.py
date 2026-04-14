# run.py
import asyncio
import json
import os
import io
from aiohttp import web, WSMsgType
from pathlib import Path
import matplotlib.pyplot as plt

# Import your poller
from sensors.esp32_poller import ESP32Poller

ROOT = Path(__file__).parent
STATIC_DIR = ROOT / "static"

# Global websockets list
WS_CLIENTS: set[web.WebSocketResponse] = set()


# ===================================================================
#                       STATIC HTML
# ===================================================================
async def index(request):
    return web.FileResponse(STATIC_DIR / "index.html")


# ===================================================================
#                       WEBSOCKET HANDLER
# ===================================================================
async def ws_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    WS_CLIENTS.add(ws)
    print("WS: client connected, total:", len(WS_CLIENTS))

    # send last payload once
    try:
        payload = getattr(request.app, "last_payload", None)
        if payload:
            await ws.send_str(json.dumps(payload))
    except:
        pass

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                if msg.data == "ping":
                    await ws.send_str("pong")
            elif msg.type == WSMsgType.ERROR:
                print("WS error:", ws.exception())
    finally:
        WS_CLIENTS.discard(ws)
        print("WS: client disconnected, total:", len(WS_CLIENTS))

    return ws


# ===================================================================
#                       LIVE GRAPH ENDPOINTS
# ===================================================================
def make_plot(x, y, title, ylabel, color="blue"):
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.plot(x, y, color=color, linewidth=2)
    ax.set_title(title)
    ax.set_xlabel("Timestamp")
    ax.set_ylabel(ylabel)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    return buf.getvalue()


async def plot_bpm(request):
    poller = request.app["esp_poller"]
    data = poller.manager.history[-300:]

    x = [s["timestamp"] for s in data]
    y = [s["bpm"] for s in data]

    img = make_plot(x, y, "BPM over Time", "BPM", "cyan")
    return web.Response(body=img, content_type="image/png")


async def plot_gsr(request):
    poller = request.app["esp_poller"]
    data = poller.manager.history[-300:]

    x = [s["timestamp"] for s in data]
    y = [s["gsr"] for s in data]

    img = make_plot(x, y, "GSR over Time", "GSR", "orange")
    return web.Response(body=img, content_type="image/png")


async def plot_stress(request):
    poller = request.app["esp_poller"]
    data = poller.manager.history[-300:]

    x = [s["timestamp"] for s in data]
    y = [s["stress"] for s in data]

    img = make_plot(x, y, "Stress over Time", "Stress", "red")
    return web.Response(body=img, content_type="image/png")


# ===================================================================
#                PAYLOAD BROADCAST LOOP
# ===================================================================
async def broadcast_loop(app):
    print("Broadcast loop started")
    last_sent = None
    import sensors.esp32_poller as poller_mod

    while True:
        try:
            payload = getattr(poller_mod, "LAST_PAYLOAD", None)

            if payload is not None and payload != last_sent:
                last_sent = payload
                app["last_payload"] = payload
                text = json.dumps(payload, default=str)

                remove = []
                for ws in list(WS_CLIENTS):
                    if ws.closed:
                        remove.append(ws)
                        continue
                    try:
                        await ws.send_str(text)
                    except:
                        remove.append(ws)

                for r in remove:
                    WS_CLIENTS.discard(r)

                print("WS broadcast:", payload)

        except Exception as e:
            print("Broadcast loop error:", e)

        await asyncio.sleep(0.5)


# ===================================================================
#                START & STOP POLLERS
# ===================================================================
async def start_background_pollers(app):
    loop = asyncio.get_event_loop()
    poller = ESP32Poller()
    poller.start(loop)
    app["esp_poller"] = poller

    app["bcast_task"] = loop.create_task(broadcast_loop(app))
    print("Started ESP32Poller and broadcast loop")


async def cleanup_background(app):
    poller = app.get("esp_poller")
    if poller:
        poller.stop()

    task = app.get("bcast_task")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    for ws in list(WS_CLIENTS):
        await ws.close()


# ===================================================================
#                      CREATE APP
# ===================================================================
def create_app():
    app = web.Application()

    # main dashboard
    app.router.add_get("/", index)
    app.router.add_get("/ws", ws_handler)

    # live graph endpoints
    app.router.add_get("/plot/bpm", plot_bpm)
    app.router.add_get("/plot/gsr", plot_gsr)
    app.router.add_get("/plot/stress", plot_stress)

    # static folder for index.html
    app.router.add_static("/static/", path=str(STATIC_DIR), name="static")

    # startup & cleanup
    app.on_startup.append(start_background_pollers)
    app.on_cleanup.append(cleanup_background)

    return app


# ===================================================================
#                      RUN SERVER
# ===================================================================
if __name__ == "__main__":
    if not STATIC_DIR.exists():
        os.makedirs(STATIC_DIR, exist_ok=True)

    app = create_app()
    web.run_app(app, host="0.0.0.0", port=8000)
