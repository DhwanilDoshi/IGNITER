"""
Data fusion engine.

Combines gaze dwell times, camera emotion/eye data, and ESP32 physiological
signals into a single structured result per session. Also generates:
  - Per-part emotion breakdown
  - AI insights (text cards for the report)
  - Targeted survey questions based on top-viewed parts
"""
import time
from collections import defaultdict
from typing import Any, Dict, List

from session import Session

# ─── Targeted survey questions per hotspot ────────────────────────────────────

PART_QUESTIONS: Dict[str, List[str]] = {
    "Steering Wheel": [
        "How comfortable did the steering wheel feel in terms of size and grip?",
        "Would you prefer a different steering wheel material or design?",
    ],
    "Cluster": [
        "Could you read the instrument cluster clearly at a glance?",
        "Is the information displayed on the cluster sufficient for your needs?",
    ],
    "Infotainment": [
        "How intuitive does the infotainment screen layout appear to you?",
        "Was the infotainment screen positioned at a comfortable viewing angle?",
    ],
    "AC": [
        "Are the AC controls easily accessible from the driver's seated position?",
        "How would you rate the visibility and placement of the AC vents?",
    ],
    "Gear": [
        "How natural does the gear/shift selector placement feel?",
        "Would you prefer a different type of gear control (toggle, dial, buttons)?",
    ],
    "Handrest": [
        "Is the center console armrest at a comfortable height?",
        "Does the storage inside the handrest area meet your expectations?",
    ],
    "Accelerator/Brake": [
        "Does the pedal placement look ergonomically correct for comfortable driving?",
        "Does the pedal area appear spacious enough for extended drives?",
    ],
    "Driver Door": [
        "Are the window/lock controls on the driver door well-positioned?",
        "Does the door panel design feel premium and intuitive?",
    ],
    "Windshield": [
        "How is the forward visibility through the windshield from the driver seat?",
        "Does the A-pillar design obstruct your view at intersections?",
    ],
    "Passenger Dashboard": [
        "Does the passenger side feel balanced and cohesive with the driver side?",
        "Are there enough features and storage on the passenger side?",
    ],
    "Passenger Door": [
        "Are the passenger door controls conveniently placed?",
        "Does the passenger door panel match the overall interior quality?",
    ],
    "Passenger Seat": [
        "Does the passenger seat appear as comfortable as the driver seat?",
        "Are passenger seat adjustments easily accessible?",
    ],
    "Driver Seat": [
        "How comfortable does the driver seat shape and bolstering appear?",
        "Does the seat provide adequate lumbar support for long drives?",
    ],
    "Sun Visor": [
        "Is the sun visor sized adequately to block glare effectively?",
        "Would you want a vanity mirror or additional sun protection features?",
    ],
    "Rear View Mirror": [
        "Is the rear view mirror well-positioned without obstructing forward vision?",
        "Would you prefer a digital camera-based mirror over a traditional one?",
    ],
    "Back Seat": [
        "Does the rear cabin appear spacious enough for adult passengers?",
        "How would you rate the rear seat comfort and available features?",
    ],
    "Sunroof": [
        "Does the sunroof / panoramic roof enhance the cabin ambiance for you?",
        "Would the sunroof feature influence your purchase decision?",
    ],
}

GENERAL_QUESTIONS = [
    "Overall, how would you rate the EV interior design on a scale of 1–10?",
    "What single feature impressed you most about this interior?",
    "What is the one thing you would change about this interior design?",
    "Would this interior design influence you to consider purchasing this EV?",
]

NEGATIVE_EMOTIONS = {"Angry", "Disgust", "Fear", "Sad"}
POSITIVE_EMOTIONS = {"Happy", "Surprise"}

# ─── Insight generation ───────────────────────────────────────────────────────

def _generate_insights(
    top_parts: List[Dict],
    part_detail: Dict,
    dominant_emotion: str,
    avg_stress: float | None,
    distraction_rate: float,
    blink_rate: float,
) -> List[str]:
    insights = []

    if top_parts:
        p = top_parts[0]
        insights.append(
            f"User focused most on '{p['part']}' ({p['validated_seconds']}s of validated gaze) — "
            "this area is a high-priority design element for this user segment."
        )

    for entry in top_parts[:3]:
        part = entry["part"]
        detail = part_detail.get(part, {})
        emo = detail.get("dominant_emotion", "")
        if emo in POSITIVE_EMOTIONS:
            insights.append(
                f"Positive reaction ({emo}) detected while viewing '{part}' — current design resonates well."
            )
        elif emo in NEGATIVE_EMOTIONS:
            insights.append(
                f"Negative reaction ({emo}) detected while viewing '{part}' — may indicate a design concern worth investigating."
            )

    if avg_stress is not None:
        if avg_stress > 0.65:
            insights.append(
                f"Elevated physiological stress (avg {avg_stress:.2f}) throughout the session — "
                "the experience may have felt overwhelming. Consider simplifying key controls."
            )
        elif avg_stress < 0.35:
            insights.append(
                f"Low stress levels (avg {avg_stress:.2f}) — user was relaxed during the experience, "
                "indicating a comfortable and intuitive interior layout."
            )

    if distraction_rate > 30:
        insights.append(
            f"High distraction rate ({distraction_rate}%) — user frequently looked away from the screen. "
            "Consider adding guided focus cues or reducing session duration."
        )
    elif distraction_rate < 10:
        insights.append(
            f"Low distraction rate ({distraction_rate}%) — user stayed highly engaged throughout the session."
        )

    if blink_rate < 8:
        insights.append(
            "Very low blink rate suggests deep visual engagement (possible eye strain risk for long sessions)."
        )
    elif blink_rate > 25:
        insights.append(
            "Elevated blink rate may indicate eye fatigue or visual discomfort with the display setup."
        )

    return insights


# ─── Main fusion function ─────────────────────────────────────────────────────

def fuse(session: Session) -> Dict[str, Any]:
    gaze    = session.gaze_events
    sensors = session.sensor_samples
    camera  = session.camera_frames

    # ── Dwell time per part ──────────────────────────────────────────────────
    raw_dwell:       Dict[str, float]             = defaultdict(float)
    validated_dwell: Dict[str, float]             = defaultdict(float)
    emotion_by_part: Dict[str, Dict[str, int]]    = defaultdict(lambda: defaultdict(int))

    for ev in gaze:
        raw_dwell[ev.part]       += 0.2   # each tick = 200 ms
        if ev.validated:
            validated_dwell[ev.part] += 0.2
        emotion_by_part[ev.part][ev.emotion] += 1

    top_parts = sorted(validated_dwell.items(), key=lambda x: x[1], reverse=True)

    # ── Per-part summary ────────────────────────────────────────────────────
    part_detail: Dict[str, Any] = {}
    for part, counts in emotion_by_part.items():
        dominant = max(counts, key=counts.get) if counts else "unknown"
        part_detail[part] = {
            "dominant_emotion":  dominant,
            "emotion_counts":    dict(counts),
            "dwell_seconds":     round(raw_dwell[part], 1),
            "validated_seconds": round(validated_dwell[part], 1),
        }

    # ── Overall emotion distribution ────────────────────────────────────────
    overall_emotions: Dict[str, int] = defaultdict(int)
    for frame in camera:
        if frame.emotion and frame.emotion != "unknown":
            overall_emotions[frame.emotion] += 1
    dominant_emotion = (
        max(overall_emotions, key=overall_emotions.get) if overall_emotions else "unknown"
    )

    # ── Blink detection via EAR threshold ───────────────────────────────────
    BLINK_THRESHOLD = 0.25
    blinks = 0
    was_closed = False
    for frame in camera:
        if frame.ear_left and frame.ear_right:
            ear = (frame.ear_left + frame.ear_right) / 2
            if ear < BLINK_THRESHOLD and not was_closed:
                blinks += 1
                was_closed = True
            elif ear >= BLINK_THRESHOLD:
                was_closed = False

    duration = session.duration
    blink_rate = round((blinks / duration) * 60, 1) if duration > 0 else 0.0

    # ── Distraction rate ────────────────────────────────────────────────────
    total_cam = len(camera)
    distracted = sum(1 for f in camera if f.gaze_direction != "center")
    distraction_pct = round((distracted / total_cam) * 100, 1) if total_cam > 0 else 0.0

    # ── Physiological stats ─────────────────────────────────────────────────
    avg_stress  = round(sum(s.ml_stress for s in sensors) / len(sensors), 3) if sensors else None
    peak_stress = round(max((s.ml_stress for s in sensors), default=0.0), 3)
    avg_bpm     = round(sum(s.bpm for s in sensors) / len(sensors), 1) if sensors else None
    avg_gsr     = round(sum(s.gsr for s in sensors) / len(sensors), 1) if sensors else None

    # Stress correlated to top-3 parts (by overlapping timestamps)
    stress_during_top: Dict[str, float] = {}
    if sensors:
        for part, _ in top_parts[:3]:
            part_ts = [ev.timestamp for ev in gaze if ev.part == part]
            if part_ts:
                t0, t1 = min(part_ts), max(part_ts)
                s_slice = [s.ml_stress for s in sensors if t0 <= s.timestamp <= t1]
                if s_slice:
                    stress_during_top[part] = round(sum(s_slice) / len(s_slice), 3)

    # Stress timeline (sampled every 5 s for chart)
    stress_timeline = []
    if sensors:
        step = 5.0
        t0 = sensors[0].timestamp
        t1 = sensors[-1].timestamp
        t = t0
        while t <= t1:
            bucket = [s.ml_stress for s in sensors if t <= s.timestamp < t + step]
            if bucket:
                stress_timeline.append({
                    "t": round(t - t0, 1),
                    "stress": round(sum(bucket) / len(bucket), 3),
                })
            t += step

    # ── Survey questions ────────────────────────────────────────────────────
    top_part_names = [p for p, _ in top_parts[:3]]
    survey_questions: List[Dict[str, str]] = []
    for part in top_part_names:
        for q in PART_QUESTIONS.get(part, [])[:2]:
            survey_questions.append({"part": part, "question": q})
    for q in GENERAL_QUESTIONS:
        survey_questions.append({"part": "general", "question": q})

    # ── Insights ────────────────────────────────────────────────────────────
    insights = _generate_insights(
        top_parts=[{"part": p, "validated_seconds": round(v, 1)} for p, v in top_parts[:5]],
        part_detail=part_detail,
        dominant_emotion=dominant_emotion,
        avg_stress=avg_stress,
        distraction_rate=distraction_pct,
        blink_rate=blink_rate,
    )

    return {
        "session_id":             session.session_id,
        "user":                   session.user,
        "duration_seconds":       duration,
        "top_parts":              [{"part": p, "validated_seconds": round(v, 1)} for p, v in top_parts],
        "part_detail":            part_detail,
        "dominant_emotion":       dominant_emotion,
        "emotion_distribution":   dict(overall_emotions),
        "blink_rate_per_min":     blink_rate,
        "distraction_rate_pct":   distraction_pct,
        "avg_stress":             avg_stress,
        "peak_stress":            peak_stress,
        "avg_bpm":                avg_bpm,
        "avg_gsr":                avg_gsr,
        "stress_during_top_parts": stress_during_top,
        "stress_timeline":        stress_timeline,
        "survey_questions":       survey_questions,
        "insights":               insights,
        "camera_frame_count":     total_cam,
        "sensor_sample_count":    len(sensors),
        "gaze_event_count":       len(gaze),
    }
