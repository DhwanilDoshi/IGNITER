"""
Session store and data models for the IGNITER pipeline.
Each user run = one Session. All streams (gaze, camera, sensor) are
appended here in real-time and fused at session end.
"""
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GazeEvent:
    """One 200-ms hotspot tick from the browser viewer."""
    timestamp: float
    part: str               # hotspot label, e.g. "Infotainment"
    validated: bool         # True when camera says gaze_direction == "center"
    emotion: str            # current emotion label at this moment
    ear_avg: float          # average eye-aspect-ratio (blink proxy)


@dataclass
class SensorSample:
    """One ESP32 poll result (BPM + GSR + derived stress)."""
    timestamp: float
    bpm: float
    gsr: float
    stress: float           # physiology-based (SensorManager)
    ml_stress: float        # rule-based predictor (ESP32StressPredictor)
    stress_level: str       # "low" / "medium" / "high"


@dataclass
class CameraFrame:
    """One frame from the camera client (eye tracking + emotion)."""
    timestamp: float
    emotion: str
    emotion_confidence: float
    gaze_direction: str     # "center" / "left" / "right"
    ear_left: float
    ear_right: float


@dataclass
class Session:
    session_id: str
    user: Dict[str, Any]
    started_at: float
    ended_at: Optional[float] = None
    gaze_events:      List[GazeEvent]    = field(default_factory=list)
    sensor_samples:   List[SensorSample] = field(default_factory=list)
    camera_frames:    List[CameraFrame]  = field(default_factory=list)
    survey_responses: Optional[Dict[str, Any]]  = None
    fusion_result:    Optional[Dict[str, Any]]  = None

    @property
    def duration(self) -> float:
        end = self.ended_at or time.time()
        return round(end - self.started_at, 1)


class SessionStore:
    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    def create(self, user: Dict[str, Any]) -> Session:
        sid = str(uuid.uuid4())[:8].upper()
        session = Session(session_id=sid, user=user, started_at=time.time())
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def end(self, session_id: str) -> Optional[Session]:
        session = self._sessions.get(session_id)
        if session and session.ended_at is None:
            session.ended_at = time.time()
        return session

    def active_sessions(self) -> List[Session]:
        return [s for s in self._sessions.values() if s.ended_at is None]
