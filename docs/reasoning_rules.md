# Reasoning Rules — SilentSense

## Overview

The reasoning engine is pure deterministic Python. It evaluates the current `AppState` snapshot and
returns the highest-priority `SituationFlag`. It has no I/O, no randomness, no LLM calls.

The LLM converts the flag into language. The rules determine what the flag IS.

---

## Situation Flags (Priority Order — Highest First)

| Priority | Flag | Urgency | Description |
|---|---|---|---|
| 1 | `SUDDEN_IMPACT` | critical | Glass break or sudden crash |
| 2 | `CHILD_DISTRESS` | critical | Child crying detected |
| 3 | `ALARM_ESCALATING` | high | Alarm beeping 3+ times in 30s |
| 4 | `RAISED_VOICES_DETECTED` | high | Shouting/argument sounds |
| 5 | `ARRIVAL_DETECTED` | medium | Footsteps → door within 12s |
| 6 | `KNOCK_OR_BELL` | medium | Door knock or doorbell |
| 7 | `WATER_RUNNING_LONG` | medium | Water running > 90s |
| 8 | `ALARM_SINGLE` | medium | Alarm detected once |
| 9 | `WATER_RUNNING_BRIEF` | low | Water running 20–90s |
| 10 | `FOOTSTEPS_ONLY` | low | Footsteps without door event |
| 11 | `CALM_AMBIENT` | low | Only birds or silence |
| 12 | `NONE` | low | No significant events |

The engine evaluates all rules and returns the **first match** in priority order.

---

## Rule Definitions

### Rule 1: SUDDEN_IMPACT

```python
def rule_sudden_impact(state: AppState, now: float) -> bool:
    """Glass break detected within the last 5 seconds."""
    last = state.class_state["glass_break"].last_seen
    return last is not None and (now - last) <= 5.0
```

**Thresholds:** 5 second recency window. No repetition needed — single event is enough.
**Urgency:** critical
**Rationale:** Glass breaking is always an immediate safety signal.

---

### Rule 2: CHILD_DISTRESS

```python
def rule_child_distress(state: AppState, now: float) -> bool:
    """Child crying detected in last 10 seconds."""
    last = state.class_state["child_crying"].last_seen
    return last is not None and (now - last) <= 10.0
```

**Thresholds:** 10 second window.
**Urgency:** critical
**Rationale:** A crying child is always high priority for a deaf user who cannot hear it naturally.

---

### Rule 3: ALARM_ESCALATING

```python
def rule_alarm_escalating(state: AppState) -> bool:
    """Alarm beep detected 3 or more times in the last 30 seconds."""
    return state.class_state["alarm_beep"].count_30s >= 3
```

**Thresholds:** 3 detections in 30s window.
**Urgency:** high
**Rationale:** A single beep may be an oven timer. Three beeps in 30 seconds suggests a real alarm.

---

### Rule 4: RAISED_VOICES_DETECTED

```python
def rule_raised_voices(state: AppState, now: float) -> bool:
    """Raised voices or shouting detected within the last 15 seconds."""
    last = state.class_state["raised_voices"].last_seen
    return last is not None and (now - last) <= 15.0
```

**Thresholds:** 15 second recency window.
**Urgency:** high
**Rationale:** Shouting may indicate conflict or someone trying to get attention.

---

### Rule 5: ARRIVAL_DETECTED

```python
def rule_arrival_detected(state: AppState) -> bool:
    """
    Footsteps detected, then door_open within 12 seconds.
    Both must have been seen within the last 30 seconds total.
    """
    footsteps_last = state.class_state["footsteps"].last_seen
    door_last = state.class_state["door_open"].last_seen

    if footsteps_last is None or door_last is None:
        return False

    # Door must come AFTER footsteps
    if door_last <= footsteps_last:
        return False

    # Gap between footsteps and door must be <= 12 seconds
    gap = door_last - footsteps_last
    if gap > 12.0:
        return False

    # Both must be recent (within last 30 seconds)
    now = time.time()  # passed in from engine in real impl
    return (now - footsteps_last) <= 30.0
```

**Thresholds:** footsteps → door within 12s, both within last 30s.
**Urgency:** medium
**Rationale:** The sequence is the signal. Door alone = door banging in wind. Footsteps then door = likely a person.

---

### Rule 6: KNOCK_OR_BELL

```python
def rule_knock_or_bell(state: AppState, now: float) -> bool:
    """Door knock or doorbell detected in last 15 seconds."""
    knock_last = state.class_state["door_knock"].last_seen
    bell_last = state.class_state["doorbell"].last_seen

    knock_recent = knock_last is not None and (now - knock_last) <= 15.0
    bell_recent = bell_last is not None and (now - bell_last) <= 15.0

    return knock_recent or bell_recent
```

**Thresholds:** 15 second window.
**Urgency:** medium
**Rationale:** Someone at the door needs immediate attention.

---

### Rule 7: WATER_RUNNING_LONG

```python
def rule_water_running_long(state: AppState) -> bool:
    """Water has been running continuously for more than 90 seconds."""
    cs = state.class_state["water_running"]
    return cs.currently_active and cs.duration_active_s > 90.0
```

**Thresholds:** 90 seconds of continuous detection.
**Urgency:** medium
**Rationale:** 90s is long enough to rule out someone washing hands. Likely forgotten tap.

---

### Rule 8: ALARM_SINGLE

```python
def rule_alarm_single(state: AppState, now: float) -> bool:
    """Alarm beep detected once or twice in last 30 seconds."""
    cs = state.class_state["alarm_beep"]
    last = cs.last_seen
    recent = last is not None and (now - last) <= 30.0
    return recent and cs.count_30s in (1, 2)
```

**Thresholds:** 1–2 detections in 30s.
**Urgency:** medium
**Rationale:** Could be an oven timer or notification. Worth noting but not escalating.

---

### Rule 9: WATER_RUNNING_BRIEF

```python
def rule_water_running_brief(state: AppState) -> bool:
    """Water has been running for 20 to 90 seconds."""
    cs = state.class_state["water_running"]
    return cs.currently_active and 20.0 <= cs.duration_active_s <= 90.0
```

**Thresholds:** 20–90 seconds.
**Urgency:** low
**Rationale:** Normal usage window. Just informational.

---

### Rule 10: FOOTSTEPS_ONLY

```python
def rule_footsteps_only(state: AppState, now: float) -> bool:
    """Footsteps detected recently without an associated door event."""
    footsteps_last = state.class_state["footsteps"].last_seen
    door_last = state.class_state["door_open"].last_seen

    if footsteps_last is None:
        return False

    footsteps_recent = (now - footsteps_last) <= 15.0

    # Only fire if no door event followed the footsteps
    no_door_after = door_last is None or door_last < footsteps_last
    return footsteps_recent and no_door_after
```

**Thresholds:** Footsteps in last 15s, no door event after.
**Urgency:** low
**Rationale:** Someone is moving nearby but has not entered through a door.

---

### Rule 11: CALM_AMBIENT

```python
def rule_calm_ambient(state: AppState, now: float) -> bool:
    """Only birds or very low-confidence ambient sounds in last 30 seconds."""
    # No high-priority events in recent window
    high_priority = [
        "glass_break", "child_crying", "alarm_beep",
        "raised_voices", "door_open", "door_knock", "doorbell"
    ]
    for label in high_priority:
        last = state.class_state[label].last_seen
        if last is not None and (now - last) <= 30.0:
            return False

    # Birds must be active
    birds_last = state.class_state["birds"].last_seen
    return birds_last is not None and (now - birds_last) <= 20.0
```

**Urgency:** low
**Rationale:** Useful to show the system is running even when nothing urgent is happening.

---

## Reasoning Engine Evaluation Order

```python
def evaluate(state: AppState, now: float) -> SituationFlag:
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
```

---

## Duration Tracking — How It Works

Duration is tracked in the state manager, not the reasoning engine.

For sustained sounds (water_running, birds):

```python
# In StateManager.add_event():
cs = self.class_state[event.label]

if not cs.currently_active:
    cs.duration_start = event.timestamp
    cs.currently_active = True

cs.last_seen = event.timestamp
cs.duration_active_s = event.timestamp - cs.duration_start

# In StateManager — decay check (called every 4 seconds by scenario engine tick):
for label, cs in self.class_state.items():
    if cs.currently_active and cs.last_seen is not None:
        if (now - cs.last_seen) > 4.0:  # 4s gap = sound stopped
            cs.currently_active = False
            cs.duration_active_s = 0.0
            cs.duration_start = None
```

---

## Repetition Tracking — How It Works

Counts are computed dynamically from the event_log deque, not stored as counters.

```python
def get_count(self, label: str, window_s: float, now: float) -> int:
    """Count events for a label within the last window_s seconds."""
    cutoff = now - window_s
    return sum(
        1 for e in self.event_log
        if e.label == label and e.timestamp >= cutoff
    )
```

This is recomputed on demand. Simple, correct, no stale counter bugs.

---

## LLM Prompt Template Per Flag

The reasoning engine returns only the flag. The explainer constructs the prompt:

```python
FLAG_PROMPTS = {
    SituationFlag.ARRIVAL_DETECTED: (
        "Footsteps were detected, followed by a door opening. "
        "Suggest someone may have entered. Be calm and brief."
    ),
    SituationFlag.ALARM_ESCALATING: (
        f"An alarm has beeped {count} times in the last 30 seconds. "
        "Suggest this may need attention. Urgent but not panicked."
    ),
    SituationFlag.WATER_RUNNING_LONG: (
        f"Water has been running for {int(duration)}  seconds. "
        "Suggest checking if it was left on."
    ),
    SituationFlag.CHILD_DISTRESS: (
        "A child crying sound was detected. "
        "Gently alert the user to check on a child nearby."
    ),
    SituationFlag.SUDDEN_IMPACT: (
        "A sudden sharp sound like breaking glass was detected. "
        "Alert the user calmly."
    ),
    SituationFlag.CALM_AMBIENT: (
        "Only calm outdoor sounds like birds detected. "
        "Reassure the user the environment appears quiet."
    ),
    # ... etc
}
```
