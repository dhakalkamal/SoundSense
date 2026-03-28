"""Tests for the reasoning engine using directly constructed AppState objects."""

import pytest

from app.models.schemas import (
    AppState,
    ClassState,
    SituationFlag,
    SoundEvent,
    UrgencyLevel,
)
from app.reasoning.engine import ReasoningEngine

engine = ReasoningEngine()

ALL_LABELS = [
    "footsteps", "door_open", "door_knock", "doorbell", "alarm_beep",
    "water_running", "birds", "glass_break", "raised_voices", "child_crying",
]


def make_state(**overrides: ClassState) -> AppState:
    """Build an AppState with all labels defaulted to empty ClassState.

    Pass keyword args of label=ClassState(...) to override specific labels.
    """
    class_state = {label: ClassState(label=label) for label in ALL_LABELS}
    class_state.update(overrides)
    return AppState(
        scenario_running=None,
        scenario_start_time=None,
        scenario_elapsed_s=None,
        event_log=[],
        class_state=class_state,
        active_situation=SituationFlag.NONE,
        active_explanation=None,
        urgency=UrgencyLevel.low,
        flag_changed_at=None,
        previous_flag=None,
        alert_history=[],
    )


# ── Test 1: footsteps at t=0, door_open at t=8 → ARRIVAL_DETECTED ──────────

def test_arrival_detected_footsteps_then_door():
    """Footsteps at t=0, door_open at t=8, evaluated at t=15 → ARRIVAL_DETECTED."""
    state = make_state(
        footsteps=ClassState(label="footsteps", last_seen=0.0),
        door_open=ClassState(label="door_open", last_seen=8.0),
    )
    result = engine.evaluate(state, now=15.0)
    assert result == SituationFlag.ARRIVAL_DETECTED


# ── Test 2: footsteps at t=0, no door → FOOTSTEPS_ONLY ─────────────────────

def test_footsteps_only_no_door():
    """Footsteps at t=0, no door event, evaluated at t=10 → FOOTSTEPS_ONLY."""
    state = make_state(
        footsteps=ClassState(label="footsteps", last_seen=0.0),
    )
    result = engine.evaluate(state, now=10.0)
    assert result == SituationFlag.FOOTSTEPS_ONLY


# ── Test 3: alarm_beep 3 times in 20 seconds → ALARM_ESCALATING ─────────────

def test_alarm_escalating_three_beeps():
    """alarm_beep count_30s=3 → ALARM_ESCALATING."""
    state = make_state(
        alarm_beep=ClassState(label="alarm_beep", last_seen=0.0, count_30s=3),
    )
    result = engine.evaluate(state, now=5.0)
    assert result == SituationFlag.ALARM_ESCALATING


# ── Test 4: water_running active for 100 seconds → WATER_RUNNING_LONG ───────

def test_water_running_long():
    """water_running active for 100s → WATER_RUNNING_LONG."""
    state = make_state(
        water_running=ClassState(
            label="water_running",
            currently_active=True,
            duration_active_s=100.0,
            last_seen=0.0,
        ),
    )
    result = engine.evaluate(state, now=5.0)
    assert result == SituationFlag.WATER_RUNNING_LONG


# ── Test 5: glass_break at t=0, evaluated at t=3 → SUDDEN_IMPACT ───────────

def test_sudden_impact_within_window():
    """glass_break at t=0, now=3 (within 5s) → SUDDEN_IMPACT."""
    state = make_state(
        glass_break=ClassState(label="glass_break", last_seen=0.0),
    )
    result = engine.evaluate(state, now=3.0)
    assert result == SituationFlag.SUDDEN_IMPACT


# ── Test 6: glass_break at t=0, evaluated at t=8 → NOT SUDDEN_IMPACT ───────

def test_sudden_impact_expired():
    """glass_break at t=0, now=8 (> 5s window) → should NOT be SUDDEN_IMPACT."""
    state = make_state(
        glass_break=ClassState(label="glass_break", last_seen=0.0),
    )
    result = engine.evaluate(state, now=8.0)
    assert result != SituationFlag.SUDDEN_IMPACT


# ── Test 7: birds active, no other events → CALM_AMBIENT ────────────────────

def test_calm_ambient_birds_only():
    """birds seen at t=0, no high-priority events, now=10 → CALM_AMBIENT."""
    state = make_state(
        birds=ClassState(label="birds", last_seen=0.0),
    )
    result = engine.evaluate(state, now=10.0)
    assert result == SituationFlag.CALM_AMBIENT


# ── Test 8: child_crying at t=0, evaluated at t=5 → CHILD_DISTRESS ──────────

def test_child_distress_within_window():
    """child_crying at t=0, now=5 (within 10s) → CHILD_DISTRESS."""
    state = make_state(
        child_crying=ClassState(label="child_crying", last_seen=0.0),
    )
    result = engine.evaluate(state, now=5.0)
    assert result == SituationFlag.CHILD_DISTRESS


# ── Additional edge-case tests ───────────────────────────────────────────────

def test_arrival_not_detected_if_door_before_footsteps():
    """Door before footsteps should not trigger ARRIVAL_DETECTED."""
    state = make_state(
        footsteps=ClassState(label="footsteps", last_seen=10.0),
        door_open=ClassState(label="door_open", last_seen=5.0),
    )
    result = engine.evaluate(state, now=15.0)
    assert result != SituationFlag.ARRIVAL_DETECTED


def test_arrival_not_detected_if_gap_too_large():
    """Footsteps → door with >12s gap should not trigger ARRIVAL_DETECTED."""
    state = make_state(
        footsteps=ClassState(label="footsteps", last_seen=0.0),
        door_open=ClassState(label="door_open", last_seen=15.0),
    )
    result = engine.evaluate(state, now=20.0)
    assert result != SituationFlag.ARRIVAL_DETECTED


def test_alarm_single_one_beep():
    """alarm_beep count_30s=1, last_seen recent → ALARM_SINGLE."""
    state = make_state(
        alarm_beep=ClassState(label="alarm_beep", last_seen=0.0, count_30s=1),
    )
    result = engine.evaluate(state, now=5.0)
    assert result == SituationFlag.ALARM_SINGLE


def test_water_running_brief():
    """water_running active for 50s → WATER_RUNNING_BRIEF."""
    state = make_state(
        water_running=ClassState(
            label="water_running",
            currently_active=True,
            duration_active_s=50.0,
            last_seen=0.0,
        ),
    )
    result = engine.evaluate(state, now=5.0)
    assert result == SituationFlag.WATER_RUNNING_BRIEF


def test_none_when_no_events():
    """No events at all → NONE."""
    state = make_state()
    result = engine.evaluate(state, now=100.0)
    assert result == SituationFlag.NONE
