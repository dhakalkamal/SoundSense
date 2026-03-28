"""Deterministic rule-based reasoning engine.

Evaluates AppState and returns the highest-priority SituationFlag.
No I/O, no async, no LLM calls.
"""

import time

from app.models.schemas import (
    AppState,
    ExplainerContext,
    SituationFlag,
    UrgencyLevel,
)

# Priority-ordered list of (flag, urgency) for metadata lookup
FLAG_URGENCY: dict[SituationFlag, UrgencyLevel] = {
    SituationFlag.SUDDEN_IMPACT: UrgencyLevel.critical,
    SituationFlag.CHILD_DISTRESS: UrgencyLevel.critical,
    SituationFlag.ALARM_ESCALATING: UrgencyLevel.high,
    SituationFlag.RAISED_VOICES_DETECTED: UrgencyLevel.high,
    SituationFlag.ARRIVAL_DETECTED: UrgencyLevel.medium,
    SituationFlag.KNOCK_OR_BELL: UrgencyLevel.medium,
    SituationFlag.WATER_RUNNING_LONG: UrgencyLevel.medium,
    SituationFlag.ALARM_SINGLE: UrgencyLevel.medium,
    SituationFlag.WATER_RUNNING_BRIEF: UrgencyLevel.low,
    SituationFlag.FOOTSTEPS_ONLY: UrgencyLevel.low,
    SituationFlag.CALM_AMBIENT: UrgencyLevel.low,
    SituationFlag.NONE: UrgencyLevel.low,
}


def rule_sudden_impact(state: AppState, now: float) -> bool:
    """Glass break detected within the last 5 seconds."""
    last = state.class_state["glass_break"].last_seen
    return last is not None and (now - last) <= 5.0


def rule_child_distress(state: AppState, now: float) -> bool:
    """Child crying detected in last 10 seconds."""
    last = state.class_state["child_crying"].last_seen
    return last is not None and (now - last) <= 10.0


def rule_alarm_escalating(state: AppState) -> bool:
    """Alarm beep detected 3 or more times in the last 30 seconds."""
    return state.class_state["alarm_beep"].count_30s >= 3


def rule_raised_voices(state: AppState, now: float) -> bool:
    """Raised voices or shouting detected within the last 15 seconds."""
    last = state.class_state["raised_voices"].last_seen
    return last is not None and (now - last) <= 15.0


def rule_arrival_detected(state: AppState, now: float) -> bool:
    """Footsteps detected, then door_open within 12 seconds, both within last 30s."""
    footsteps_last = state.class_state["footsteps"].last_seen
    door_last = state.class_state["door_open"].last_seen

    if footsteps_last is None or door_last is None:
        return False

    # Door must come AFTER footsteps
    if door_last <= footsteps_last:
        return False

    # Gap between footsteps and door must be <= 12 seconds
    if (door_last - footsteps_last) > 12.0:
        return False

    # Both must be recent (within last 30 seconds)
    return (now - footsteps_last) <= 30.0


def rule_knock_or_bell(state: AppState, now: float) -> bool:
    """Door knock or doorbell detected in last 15 seconds."""
    knock_last = state.class_state["door_knock"].last_seen
    bell_last = state.class_state["doorbell"].last_seen

    knock_recent = knock_last is not None and (now - knock_last) <= 15.0
    bell_recent = bell_last is not None and (now - bell_last) <= 15.0
    return knock_recent or bell_recent


def rule_water_running_long(state: AppState) -> bool:
    """Water has been running continuously for more than 90 seconds."""
    cs = state.class_state["water_running"]
    return cs.currently_active and cs.duration_active_s > 90.0


def rule_alarm_single(state: AppState, now: float) -> bool:
    """Alarm beep detected once or twice in last 30 seconds."""
    cs = state.class_state["alarm_beep"]
    last = cs.last_seen
    recent = last is not None and (now - last) <= 30.0
    return recent and cs.count_30s in (1, 2)


def rule_water_running_brief(state: AppState) -> bool:
    """Water has been running for 20 to 90 seconds."""
    cs = state.class_state["water_running"]
    return cs.currently_active and 20.0 <= cs.duration_active_s <= 90.0


def rule_footsteps_only(state: AppState, now: float) -> bool:
    """Footsteps detected recently without an associated door event after them."""
    footsteps_last = state.class_state["footsteps"].last_seen
    door_last = state.class_state["door_open"].last_seen

    if footsteps_last is None:
        return False

    footsteps_recent = (now - footsteps_last) <= 15.0
    no_door_after = door_last is None or door_last < footsteps_last
    return footsteps_recent and no_door_after


def rule_calm_ambient(state: AppState, now: float) -> bool:
    """Only birds or very low-confidence ambient sounds in last 30 seconds."""
    high_priority = [
        "glass_break", "child_crying", "alarm_beep",
        "raised_voices", "door_open", "door_knock", "doorbell",
    ]
    for label in high_priority:
        last = state.class_state[label].last_seen
        if last is not None and (now - last) <= 30.0:
            return False

    birds_last = state.class_state["birds"].last_seen
    return birds_last is not None and (now - birds_last) <= 20.0


class ReasoningEngine:
    """Evaluates AppState snapshots and returns the highest-priority SituationFlag."""

    def evaluate(self, state: AppState, now: float) -> SituationFlag:
        """Evaluate all rules in priority order and return the first match."""
        if rule_sudden_impact(state, now):
            return SituationFlag.SUDDEN_IMPACT
        if rule_child_distress(state, now):
            return SituationFlag.CHILD_DISTRESS
        if rule_alarm_escalating(state):
            return SituationFlag.ALARM_ESCALATING
        if rule_raised_voices(state, now):
            return SituationFlag.RAISED_VOICES_DETECTED
        if rule_arrival_detected(state, now):
            return SituationFlag.ARRIVAL_DETECTED
        if rule_knock_or_bell(state, now):
            return SituationFlag.KNOCK_OR_BELL
        if rule_water_running_long(state):
            return SituationFlag.WATER_RUNNING_LONG
        if rule_alarm_single(state, now):
            return SituationFlag.ALARM_SINGLE
        if rule_water_running_brief(state):
            return SituationFlag.WATER_RUNNING_BRIEF
        if rule_footsteps_only(state, now):
            return SituationFlag.FOOTSTEPS_ONLY
        if rule_calm_ambient(state, now):
            return SituationFlag.CALM_AMBIENT
        return SituationFlag.NONE

    def get_explainer_context(
        self, state: AppState, flag: SituationFlag, now: float
    ) -> ExplainerContext:
        """Build context object for the LLM explainer from current state."""
        # recent_labels: only include sounds that are relevant to the active flag.
        # Using the global last-5 events caused alarm_beep entries (from a prior
        # ALARM_ESCALATING flag) to dominate the list even after the flag changed
        # to KNOCK_OR_BELL or CHILD_DISTRESS, producing wrong explanations.
        _FLAG_RELEVANT_LABELS: dict[SituationFlag, set[str]] = {
            SituationFlag.SUDDEN_IMPACT: {"glass_break"},
            SituationFlag.CHILD_DISTRESS: {"child_crying"},
            SituationFlag.ALARM_ESCALATING: {"alarm_beep"},
            SituationFlag.ALARM_SINGLE: {"alarm_beep"},
            SituationFlag.RAISED_VOICES_DETECTED: {"raised_voices"},
            SituationFlag.ARRIVAL_DETECTED: {"footsteps", "door_open"},
            SituationFlag.KNOCK_OR_BELL: {"door_knock", "doorbell"},
            SituationFlag.WATER_RUNNING_LONG: {"water_running"},
            SituationFlag.WATER_RUNNING_BRIEF: {"water_running"},
            SituationFlag.FOOTSTEPS_ONLY: {"footsteps"},
            SituationFlag.CALM_AMBIENT: {"birds"},
        }
        relevant = _FLAG_RELEVANT_LABELS.get(flag)
        if relevant:
            recent_labels = [
                e.label for e in state.event_log if e.label in relevant
            ][-5:]
        else:
            recent_labels = [e.label for e in state.event_log[-5:]]

        # Dominant label: pinned to the sound that triggered the flag so the LLM
        # always receives an accurate primary sound rather than the most-frequent
        # label in the window (which may be a high-frequency alarm_beep drowning
        # out an unrelated triggering event like glass_break or child_crying).
        _FLAG_PRIMARY_LABEL: dict[SituationFlag, str] = {
            SituationFlag.SUDDEN_IMPACT: "glass_break",
            SituationFlag.CHILD_DISTRESS: "child_crying",
            SituationFlag.ALARM_ESCALATING: "alarm_beep",
            SituationFlag.ALARM_SINGLE: "alarm_beep",
            SituationFlag.RAISED_VOICES_DETECTED: "raised_voices",
            SituationFlag.ARRIVAL_DETECTED: "door_open",
            SituationFlag.KNOCK_OR_BELL: "door_knock",
            SituationFlag.WATER_RUNNING_LONG: "water_running",
            SituationFlag.WATER_RUNNING_BRIEF: "water_running",
            SituationFlag.FOOTSTEPS_ONLY: "footsteps",
            SituationFlag.CALM_AMBIENT: "birds",
        }
        dominant_label: str | None = _FLAG_PRIMARY_LABEL.get(flag)

        # Duration and count depend on the flag
        duration_s: float | None = None
        count: int | None = None

        if flag == SituationFlag.WATER_RUNNING_LONG or flag == SituationFlag.WATER_RUNNING_BRIEF:
            duration_s = state.class_state["water_running"].duration_active_s
        elif flag == SituationFlag.ALARM_ESCALATING or flag == SituationFlag.ALARM_SINGLE:
            count = state.class_state["alarm_beep"].count_30s

        # Time of day from current wall clock
        hour = time.localtime(now).tm_hour
        if 5 <= hour < 12:
            time_of_day = "morning"
        elif 12 <= hour < 17:
            time_of_day = "afternoon"
        elif 17 <= hour < 21:
            time_of_day = "evening"
        else:
            time_of_day = "night"

        return ExplainerContext(
            flag=flag,
            recent_labels=recent_labels,
            dominant_label=dominant_label,
            duration_s=duration_s,
            count=count,
            time_of_day=time_of_day,
        )
