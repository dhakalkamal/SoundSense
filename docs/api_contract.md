# API Contract — SilentSense

## Base URL

```
http://localhost:8000/api/v1
```

All responses are JSON. All timestamps are Unix epoch floats (seconds).

---

## Shared Types

### UrgencyLevel
```
"low" | "medium" | "high" | "critical"
```

### SituationFlag
```
"NONE" | "CALM_AMBIENT" | "FOOTSTEPS_ONLY" | "WATER_RUNNING_BRIEF" |
"ALARM_SINGLE" | "WATER_RUNNING_LONG" | "KNOCK_OR_BELL" |
"ARRIVAL_DETECTED" | "RAISED_VOICES_DETECTED" | "ALARM_ESCALATING" |
"CHILD_DISTRESS" | "SUDDEN_IMPACT"
```

### SoundEventItem (appears in timeline)
```json
{
  "label": "footsteps",
  "confidence": 0.88,
  "timestamp": 1718200012.4,
  "elapsed_s": 8.4
}
```
`elapsed_s` = seconds since scenario started (computed by backend for display convenience)

---

## Endpoints

---

### POST /scenario/start

Start a named scenario. Clears any existing state. Only one scenario runs at a time.

**Request:**
```json
{
  "scenario": "someone_enters"
}
```

**Available scenarios:**
- `someone_enters` — footsteps + door, medium urgency narrative
- `alarm_escalation` — repeated beeps escalating to critical
- `water_forgotten` — water running continuously for 2+ minutes
- `quiet_background` — birds only, calm environment
- `child_alert` — child crying suddenly
- `glass_break` — sudden impact event

**Response 200:**
```json
{
  "ok": true,
  "scenario": "someone_enters",
  "duration_s": 45,
  "message": "Scenario started. Poll /state/latest every 2 seconds."
}
```

**Response 400 (unknown scenario):**
```json
{
  "ok": false,
  "error": "Unknown scenario: 'bad_name'. Valid: [someone_enters, alarm_escalation, ...]"
}
```

---

### POST /scenario/stop

Stop the current scenario and reset all state.

**Request:** (no body)

**Response 200:**
```json
{
  "ok": true,
  "message": "Scenario stopped and state cleared."
}
```

---

### GET /scenario/list

List all available scenarios with metadata.

**Response 200:**
```json
{
  "scenarios": [
    {
      "name": "someone_enters",
      "description": "Footsteps followed by a door opening — arrival detection demo",
      "duration_s": 45,
      "peak_urgency": "medium"
    },
    {
      "name": "alarm_escalation",
      "description": "Alarm beeping repeatedly — escalation to high urgency",
      "duration_s": 35,
      "peak_urgency": "high"
    },
    {
      "name": "water_forgotten",
      "description": "Water running continuously, escalates from low to medium",
      "duration_s": 120,
      "peak_urgency": "medium"
    },
    {
      "name": "quiet_background",
      "description": "Bird sounds only — calm ambient environment",
      "duration_s": 30,
      "peak_urgency": "low"
    },
    {
      "name": "child_alert",
      "description": "Child crying suddenly — critical urgency demo",
      "duration_s": 20,
      "peak_urgency": "critical"
    },
    {
      "name": "glass_break",
      "description": "Sudden sharp impact sound — critical urgency demo",
      "duration_s": 15,
      "peak_urgency": "critical"
    }
  ]
}
```

---

### GET /state/latest

**Primary polling endpoint.** Frontend calls this every 2 seconds.

Returns the full current state of the system.

**Response 200 (scenario running):**
```json
{
  "scenario_running": "someone_enters",
  "scenario_elapsed_s": 11.2,
  "situation": {
    "flag": "ARRIVAL_DETECTED",
    "urgency": "medium",
    "explanation": "Footsteps were detected just before the door opened — someone may have entered.",
    "flag_changed_at": 1718200011.0,
    "previous_flag": "CALM_AMBIENT"
  },
  "timeline": [
    {
      "label": "birds",
      "confidence": 0.81,
      "timestamp": 1718200002.0,
      "elapsed_s": 2.0
    },
    {
      "label": "footsteps",
      "confidence": 0.88,
      "timestamp": 1718200008.0,
      "elapsed_s": 8.0
    },
    {
      "label": "door_open",
      "confidence": 0.91,
      "timestamp": 1718200011.0,
      "elapsed_s": 11.0
    }
  ],
  "raw_labels_only": ["birds", "footsteps", "door_open"],
  "active_durations": {
    "water_running": null,
    "birds": 9.2
  },
  "counts_30s": {
    "alarm_beep": 0,
    "footsteps": 1
  }
}
```

**`raw_labels_only`** — this field is specifically for the side-by-side UI panel showing "without SilentSense."

**Response 200 (no scenario running):**
```json
{
  "scenario_running": null,
  "scenario_elapsed_s": null,
  "situation": {
    "flag": "NONE",
    "urgency": "low",
    "explanation": null,
    "flag_changed_at": null,
    "previous_flag": null
  },
  "timeline": [],
  "raw_labels_only": [],
  "active_durations": {},
  "counts_30s": {}
}
```

---

### GET /state/timeline

Returns only the event timeline (for a dedicated timeline view or scroll history).

**Query params:**
- `limit` (int, default 50) — max events to return
- `since_timestamp` (float, optional) — only return events after this timestamp

**Response 200:**
```json
{
  "events": [
    {
      "label": "birds",
      "confidence": 0.81,
      "timestamp": 1718200002.0,
      "elapsed_s": 2.0
    }
  ],
  "total_count": 1
}
```

---

### GET /state/alerts

Returns only urgent/important situation changes (flag changes above low urgency).
Useful for a dedicated alerts panel or notification feed.

**Response 200:**
```json
{
  "alerts": [
    {
      "flag": "ARRIVAL_DETECTED",
      "urgency": "medium",
      "explanation": "Footsteps were detected just before the door opened — someone may have entered.",
      "timestamp": 1718200011.0,
      "elapsed_s": 11.0
    },
    {
      "flag": "ALARM_ESCALATING",
      "urgency": "high",
      "explanation": "An alarm has sounded multiple times — this may need your attention.",
      "timestamp": 1718200025.0,
      "elapsed_s": 25.0
    }
  ]
}
```

---

### GET /health

Health check. Used by frontend to verify backend is reachable.

**Response 200:**
```json
{
  "status": "ok",
  "classifier": "panns_cnn14",
  "llm_provider": "openai",
  "scenario_running": "someone_enters"
}
```

---

## Polling Strategy (Frontend Guidance)

The frontend should:
1. Call `GET /state/latest` every **2 seconds** while a scenario is running
2. Stop polling when `scenario_running` is `null`
3. Use `situation.flag_changed_at` to animate transitions (only re-render card when this value changes)
4. Use `situation.previous_flag` to show "was: X → now: Y" transition if desired
5. Use `raw_labels_only` for the side-by-side "without SilentSense" panel

---

## Urgency → UI Color Mapping (Suggested)

| Urgency | Color | Usage |
|---|---|---|
| `low` | `#22C55E` (green) | Calm, informational |
| `medium` | `#F59E0B` (amber) | Attention needed |
| `high` | `#EF4444` (red) | Urgent, action may be needed |
| `critical` | `#7C3AED` (purple) | Immediate attention, high contrast |

---

## Error Handling

All errors follow this shape:
```json
{
  "ok": false,
  "error": "Human-readable error message"
}
```

HTTP status codes: 200 success, 400 bad request, 500 internal error.
