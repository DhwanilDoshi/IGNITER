# sensors/sensor_manager.py
from typing import Dict, Any, Optional
from sensors.esp32_reader import process_sample

class SensorManager:
    """
    Fuses the processed sample and computes a baseline stress score (physiology-based).
    """
    def __init__(self) -> None:
        self.prev: Optional[Dict[str, Any]] = None
        self.history: list[Dict[str, Any]] = []

    def ingest(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        sample = process_sample(raw, prev=self.prev)

        gsr = sample.get("gsr", 0.0)
        bpm = sample.get("bpm", 0.0)
        hrv = sample.get("hrv_sdnn", 0.0)

        # Normalize bpm: map 60 -> 0, 100 -> 1 (clamped)
        bpm_score = min(max((bpm - 60.0) / 40.0, 0.0), 1.0)

        # GSR: treat > 500 as a significant rise (this threshold can be tuned)
        gsr_score = 1.0 if gsr > 500.0 else 0.0

        # HRV: when available, lower HRV indicates higher stress.
        # since HRV = 0 for dummy, hrv_score will be 1.0 (max stress) if hrv >> 0; keep safe mapping:
        hrv_score = 1.0 - min(hrv / 100.0, 1.0)

        # Weighted fusion (physiological rule-based)
        stress = round(0.6 * bpm_score + 0.3 * gsr_score + 0.1 * hrv_score, 3)
        sample["stress"] = stress

        # keep a short history
        self.prev = sample
        self.history.append(sample)
        if len(self.history) > 5000:
            self.history = self.history[-2000:]

        return sample
