"""Predefined scenario definitions for demo playback."""

from dataclasses import dataclass


@dataclass
class ScenarioEvent:
    """A single timed sound event within a scenario."""

    delay_s: float   # seconds after scenario start to emit this event
    label: str       # sound class label
    confidence: float  # fixed confidence for this event


@dataclass
class ScenarioDefinition:
    """A complete scenario with metadata and ordered event list."""

    name: str
    description: str
    duration_s: int
    peak_urgency: str
    events: list[ScenarioEvent]


SCENARIOS: dict[str, ScenarioDefinition] = {
    "someone_enters": ScenarioDefinition(
        name="someone_enters",
        description="Footsteps followed by a door opening — arrival detection demo",
        duration_s=45,
        peak_urgency="medium",
        events=[
            ScenarioEvent(delay_s=2,  label="birds",     confidence=0.81),
            ScenarioEvent(delay_s=5,  label="birds",     confidence=0.78),
            ScenarioEvent(delay_s=8,  label="footsteps", confidence=0.88),
            ScenarioEvent(delay_s=10, label="footsteps", confidence=0.85),
            ScenarioEvent(delay_s=13, label="door_open", confidence=0.91),
            ScenarioEvent(delay_s=16, label="footsteps", confidence=0.72),
            ScenarioEvent(delay_s=20, label="door_open", confidence=0.74),
        ],
    ),
    "alarm_escalation": ScenarioDefinition(
        name="alarm_escalation",
        description="Alarm beeping repeatedly — escalation to high urgency",
        duration_s=35,
        peak_urgency="high",
        events=[
            ScenarioEvent(delay_s=2,  label="birds",      confidence=0.79),
            ScenarioEvent(delay_s=6,  label="alarm_beep", confidence=0.83),
            ScenarioEvent(delay_s=12, label="alarm_beep", confidence=0.91),
            ScenarioEvent(delay_s=16, label="alarm_beep", confidence=0.88),
            ScenarioEvent(delay_s=20, label="alarm_beep", confidence=0.94),
            ScenarioEvent(delay_s=24, label="alarm_beep", confidence=0.87),
            ScenarioEvent(delay_s=28, label="alarm_beep", confidence=0.92),
        ],
    ),
    "water_forgotten": ScenarioDefinition(
        name="water_forgotten",
        description="Water running continuously, escalates from low to medium",
        duration_s=120,
        peak_urgency="medium",
        events=[
            ScenarioEvent(delay_s=3,   label="water_running", confidence=0.87),
            ScenarioEvent(delay_s=7,   label="water_running", confidence=0.91),
            ScenarioEvent(delay_s=15,  label="water_running", confidence=0.89),
            ScenarioEvent(delay_s=25,  label="water_running", confidence=0.93),
            ScenarioEvent(delay_s=35,  label="water_running", confidence=0.88),
            ScenarioEvent(delay_s=50,  label="water_running", confidence=0.91),
            ScenarioEvent(delay_s=65,  label="water_running", confidence=0.86),
            ScenarioEvent(delay_s=80,  label="water_running", confidence=0.90),
            ScenarioEvent(delay_s=95,  label="water_running", confidence=0.88),
            ScenarioEvent(delay_s=110, label="water_running", confidence=0.92),
        ],
    ),
    "quiet_background": ScenarioDefinition(
        name="quiet_background",
        description="Bird sounds only — calm ambient environment",
        duration_s=30,
        peak_urgency="low",
        events=[
            ScenarioEvent(delay_s=2,  label="birds", confidence=0.84),
            ScenarioEvent(delay_s=7,  label="birds", confidence=0.79),
            ScenarioEvent(delay_s=12, label="birds", confidence=0.86),
            ScenarioEvent(delay_s=18, label="birds", confidence=0.81),
            ScenarioEvent(delay_s=24, label="birds", confidence=0.83),
        ],
    ),
    "child_alert": ScenarioDefinition(
        name="child_alert",
        description="Child crying suddenly — critical urgency demo",
        duration_s=20,
        peak_urgency="critical",
        events=[
            ScenarioEvent(delay_s=2,  label="birds",        confidence=0.77),
            ScenarioEvent(delay_s=5,  label="birds",        confidence=0.81),
            ScenarioEvent(delay_s=9,  label="child_crying", confidence=0.94),
            ScenarioEvent(delay_s=12, label="child_crying", confidence=0.91),
            ScenarioEvent(delay_s=15, label="child_crying", confidence=0.88),
        ],
    ),
    "glass_break": ScenarioDefinition(
        name="glass_break",
        description="Sudden sharp impact sound — critical urgency demo",
        duration_s=15,
        peak_urgency="critical",
        events=[
            ScenarioEvent(delay_s=2, label="footsteps",    confidence=0.79),
            ScenarioEvent(delay_s=4, label="footsteps",    confidence=0.83),
            ScenarioEvent(delay_s=7, label="glass_break",  confidence=0.96),
            ScenarioEvent(delay_s=9, label="raised_voices", confidence=0.84),
        ],
    ),
}
