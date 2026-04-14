# sensors/esp32_reader.py
import time
from typing import Dict, Optional, Any

def process_sample(raw: Dict[str, Any], prev: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convert raw JSON from ESP32 into consistent types expected by the pipeline.
    Expects ESP32 to send at least: {"bpm": <num>, "gsr": <num>}
    """
    ts = time.time()
    # safe conversions
    try:
        gsr = float(raw.get("gsr", 0))
    except Exception:
        gsr = 0.0
    try:
        bpm = float(raw.get("bpm", 0))
    except Exception:
        bpm = 0.0

    # HRV / SDNN not available on dummy device; keep 0.0 placeholder
    hrv_sdnn = 0.0

    return {
        "gsr": gsr,
        "bpm": bpm,
        "hrv": 0.0,
        "hrv_sdnn": hrv_sdnn,
        "timestamp": ts
    }
