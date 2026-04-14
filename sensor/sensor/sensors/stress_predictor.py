# sensors/stress_predictor.py
from typing import Dict, Any

class ESP32StressPredictor:
    """
    Rule-based physiological stress predictor (Option A).
    Produces:
      - ml_stress: float 0.0-1.0
      - ml_confidence: 0.0-1.0 (heuristic)
      - stress_level: "low"/"medium"/"high"
    """

    def __init__(self):
        # any calibration parameters can be placed here
        pass

    def predict(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        # read primary signals (safe defaults)
        try:
            bpm = float(raw.get("bpm", 0.0))
        except Exception:
            bpm = 0.0
        try:
            gsr = float(raw.get("gsr", 0.0))
        except Exception:
            gsr = 0.0

        # bpm_score normalized as in SensorManager
        bpm_score = min(max((bpm - 60.0) / 40.0, 0.0), 1.0)

        # gsr_score: use a soft threshold to get partial credit
        if gsr <= 300.0:
            gsr_score = 0.0
        elif gsr >= 700.0:
            gsr_score = 1.0
        else:
            # linear interpolate between 300 and 700
            gsr_score = (gsr - 300.0) / (700.0 - 300.0)

        # Combine with weights (tunable)
        ml_stress = 0.6 * bpm_score + 0.4 * gsr_score
        # clamp
        ml_stress = max(0.0, min(1.0, round(ml_stress, 3)))

        # heuristic confidence: higher when bpm and gsr are in extreme ranges
        confidence = 0.5 + 0.5 * (bpm_score * 0.6 + gsr_score * 0.4)
        confidence = max(0.0, min(1.0, round(confidence, 3)))

        # Map to a label
        if ml_stress < 0.3:
            level = "low"
        elif ml_stress < 0.6:
            level = "medium"
        else:
            level = "high"

        return {
            "ml_stress": ml_stress,
            "ml_confidence": confidence,
            "stress_level": level
        }
