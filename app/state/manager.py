"""In-memory state manager for short-term sound event tracking."""

import time
from collections import deque

from app.models.schemas import (
    AppState,
    ClassState,
    SituationFlag,
    SoundEvent,
    UrgencyLevel,
)

SOUND_LABELS = [
    "footsteps",
    "door_open",
    "door_knock",
    "doorbell",
    "alarm_beep",
    "water_running",
    "birds",
    "glass_break",
    "raised_voices",
    "child_crying",
]


class StateManager:
    """Maintains all short-term memory of sound events.

    No reasoning or LLM calls happen here — pure event tracking only.
    """

    def __init__(self) -> None:
        """Initialize deque, per-class tracking state, and all counters."""
        self.reset()

    def reset(self) -> None:
        """Clear all state back to initial values."""
        self._event_log: deque[SoundEvent] = deque(maxlen=200)
        self._class_state: dict[str, ClassState] = {
            label: ClassState(label=label) for label in SOUND_LABELS
        }
        self._scenario_running: str | None = None
        self._scenario_start_time: float | None = None
        self._active_situation: SituationFlag = SituationFlag.NONE
        self._active_explanation: str | None = None
        self._urgency: UrgencyLevel = UrgencyLevel.low
        self._flag_changed_at: float | None = None
        self._previous_flag: SituationFlag | None = None
        self._alert_history: list[dict] = []

    def add_event(self, event: SoundEvent) -> None:
        """Append event to deque and update per-class tracking state."""
        self._event_log.append(event)

        label = event.label
        if label not in self._class_state:
            return  # unknown label — skip state update

        cs = self._class_state[label]

        if not cs.currently_active:
            cs.duration_start = event.timestamp
            cs.currently_active = True

        cs.last_seen = event.timestamp
        cs.duration_active_s = event.timestamp - cs.duration_start  # type: ignore[operator]

    def decay_inactive(self, now: float) -> None:
        """Mark labels inactive if last_seen is more than 4 seconds ago."""
        for cs in self._class_state.values():
            if cs.currently_active and cs.last_seen is not None:
                if (now - cs.last_seen) > 4.0:
                    cs.currently_active = False
                    cs.duration_active_s = 0.0
                    cs.duration_start = None

    def get_count(self, label: str, window_s: float, now: float) -> int:
        """Count events for a label within the last window_s seconds."""
        cutoff = now - window_s
        return sum(
            1 for e in self._event_log
            if e.label == label and e.timestamp >= cutoff
        )

    def get_snapshot(self) -> AppState:
        """Return a full immutable AppState snapshot with current counts."""
        now = time.time()

        snapshot_class_state: dict[str, ClassState] = {}
        for label, cs in self._class_state.items():
            snapshot_class_state[label] = ClassState(
                label=cs.label,
                last_seen=cs.last_seen,
                currently_active=cs.currently_active,
                duration_start=cs.duration_start,
                duration_active_s=cs.duration_active_s,
                count_30s=self.get_count(label, 30.0, now),
            )

        elapsed: float | None = None
        if self._scenario_start_time is not None:
            elapsed = now - self._scenario_start_time

        return AppState(
            scenario_running=self._scenario_running,
            scenario_start_time=self._scenario_start_time,
            scenario_elapsed_s=elapsed,
            event_log=list(self._event_log),
            class_state=snapshot_class_state,
            active_situation=self._active_situation,
            active_explanation=self._active_explanation,
            urgency=self._urgency,
            flag_changed_at=self._flag_changed_at,
            previous_flag=self._previous_flag,
            alert_history=list(self._alert_history),
        )

    def set_situation(
        self,
        flag: SituationFlag,
        explanation: str,
        urgency: UrgencyLevel,
        now: float,
    ) -> None:
        """Update the active situation flag, explanation, and urgency."""
        self._previous_flag = self._active_situation
        self._active_situation = flag
        self._active_explanation = explanation
        self._urgency = urgency
        self._flag_changed_at = now

    def set_scenario(self, name: str | None, start_time: float | None) -> None:
        """Set (or clear) the active scenario name and start time."""
        self._scenario_running = name
        self._scenario_start_time = start_time

    def add_alert(
        self,
        flag: SituationFlag,
        explanation: str,
        urgency: UrgencyLevel,
        elapsed_s: float,
    ) -> None:
        """Append a situation change to the alert history."""
        self._alert_history.append(
            {
                "flag": flag.value,
                "explanation": explanation,
                "urgency": urgency.value,
                "elapsed_s": elapsed_s,
                "timestamp": time.time(),
            }
        )
