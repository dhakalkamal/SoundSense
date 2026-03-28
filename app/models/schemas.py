"""All Pydantic models and enums for the SilentSense system."""

from enum import Enum
from pydantic import BaseModel, Field


class UrgencyLevel(str, Enum):
    """Urgency levels for situation alerts."""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class SituationFlag(str, Enum):
    """All possible situation flags, ordered by priority (highest first)."""

    SUDDEN_IMPACT = "SUDDEN_IMPACT"
    CHILD_DISTRESS = "CHILD_DISTRESS"
    ALARM_ESCALATING = "ALARM_ESCALATING"
    RAISED_VOICES_DETECTED = "RAISED_VOICES_DETECTED"
    ARRIVAL_DETECTED = "ARRIVAL_DETECTED"
    KNOCK_OR_BELL = "KNOCK_OR_BELL"
    WATER_RUNNING_LONG = "WATER_RUNNING_LONG"
    ALARM_SINGLE = "ALARM_SINGLE"
    WATER_RUNNING_BRIEF = "WATER_RUNNING_BRIEF"
    FOOTSTEPS_ONLY = "FOOTSTEPS_ONLY"
    CALM_AMBIENT = "CALM_AMBIENT"
    NONE = "NONE"


class SoundEvent(BaseModel):
    """A single detected sound event emitted by the inference layer."""

    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: float  # Unix epoch
    elapsed_s: float = 0.0  # seconds since scenario start, set by scenario engine


class ClassState(BaseModel):
    """Per-label tracking state maintained by the state manager."""

    label: str
    last_seen: float | None = None
    currently_active: bool = False
    duration_start: float | None = None
    duration_active_s: float = 0.0
    count_30s: int = 0  # rolling count over last 30s, computed on snapshot


class AppState(BaseModel):
    """Full application state snapshot returned by the state manager."""

    scenario_running: str | None
    scenario_start_time: float | None
    scenario_elapsed_s: float | None
    event_log: list[SoundEvent]  # last N events (deque maxlen=200)
    class_state: dict[str, ClassState]  # keyed by label
    active_situation: SituationFlag
    active_explanation: str | None
    urgency: UrgencyLevel
    flag_changed_at: float | None
    previous_flag: SituationFlag | None
    alert_history: list[dict]  # list of past situation changes


class ExplainerContext(BaseModel):
    """Context object passed to the LLM explainer."""

    flag: SituationFlag
    recent_labels: list[str]  # last 5 event labels in order
    dominant_label: str | None  # most frequent label in last 30s
    duration_s: float | None  # relevant duration if applicable
    count: int | None  # relevant repetition count if applicable
    time_of_day: str  # morning / afternoon / evening / night


class ExplainerResponse(BaseModel):
    """Response returned by the LLM explainer."""

    explanation: str
    urgency: UrgencyLevel
