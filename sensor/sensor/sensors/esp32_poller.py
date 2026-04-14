# sensors/esp32_poller.py
import aiohttp
import asyncio
import traceback
from typing import Optional

from sensors.sensor_manager import SensorManager
from sensors.stress_predictor import ESP32StressPredictor

# ------- CONFIG (edit this if your ESP IP changes) -------
ESP32_IP = "10.60.60.160"        # <- set your ESP32 IP here
ESP32_POLL_INTERVAL = 1.0        # seconds between polls
ESP32_TIMEOUT = 5                # seconds request timeout
# ---------------------------------------------------------

class ESP32Poller:
    def __init__(self):
        self.url = f"http://{ESP32_IP}/data"
        self.running = False
        self.manager = SensorManager()
        self.predictor = ESP32StressPredictor()
        self.task: Optional[asyncio.Task] = None

    async def loop(self) -> None:
        self.running = True
        print("ESP32 Poller loop started. Polling:", self.url)
        async with aiohttp.ClientSession() as session:
            while self.running:
                try:
                    async with session.get(self.url, timeout=ESP32_TIMEOUT) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            # fused processing (parses and computes stress)
                            try:
                                fused = self.manager.ingest(data) or {}
                            except Exception:
                                print("SensorManager ingest error:")
                                traceback.print_exc()
                                fused = {}

                            # predictor (rule-based model)
                            try:
                                predicted = self.predictor.predict(data) or {}
                            except Exception:
                                print("Predictor error:")
                                traceback.print_exc()
                                predicted = {}

                            # merge fused and predicted (predicted keys won't overwrite fused's 'stress' unless intended)
                            payload = {**fused, **predicted}
                            global LAST_PAYLOAD
                            LAST_PAYLOAD = payload
                            print("Broadcast:", payload)

                        else:
                            print(f"HTTP error from ESP32: {resp.status}")
                except asyncio.CancelledError:
                    raise
                except Exception:
                    print("Poller exception:")
                    traceback.print_exc()

                await asyncio.sleep(ESP32_POLL_INTERVAL)

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        if self.task is None:
            self.task = loop.create_task(self.loop())

    def stop(self) -> None:
        self.running = False
        if self.task:
            try:
                self.task.cancel()
            except Exception:
                pass
