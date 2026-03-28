# Architecture — SilentSense Backend

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    SCENARIO ENGINE                          │
│  Emits timed SoundEvent objects (fake or real audio chunks) │
└───────────────────────┬─────────────────────────────────────┘
                        │ SoundEvent(label, confidence, timestamp)
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  INFERENCE LAYER                            │
│  Fake: returns hardcoded labels                             │
│  Real: CNN14 PANNs → 527 class logits → mapped to 10 labels │
└───────────────────────┬─────────────────────────────────────┘
                        │ SoundEvent (same schema regardless of source)
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  STATE MANAGER                              │
│  Maintains rolling 120s event deque                         │
│  Tracks: counts, durations, last_seen, active flags         │
└───────────────────────┬─────────────────────────────────────┘
                        │ AppState snapshot
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  REASONING ENGINE                           │
│  Pure Python deterministic rules                            │
│  Evaluates AppState → emits SituationFlag                   │
│  Detects: sequences, repetition, duration, escalation       │
└───────────────────────┬─────────────────────────────────────┘
                        │ SituationFlag (only if CHANGED)
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  LLM EXPLAINER                              │
│  Receives: SituationFlag + compact event summary            │
│  Returns: one natural language sentence + urgency level     │
│  Providers: OpenAI (default), Gemini, Anthropic             │
└───────────────────────┬─────────────────────────────────────┘
                        │ Explanation + urgency
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  API LAYER (FastAPI)                        │
│  Assembles APIResponse from state + explanation             │
│  Serves frontend via REST polling                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Module Responsibilities

### 1. Scenario Engine (`scenario/`)

**Responsibility:** Simulate continuous listening by emitting a timed sequence of `SoundEvent` objects.

- Loads a named scenario (e.g., `someone_enters`) from `scenarios.py`
- Runs an async loop using `asyncio.sleep()` between events
- Calls the inference layer (or fake classifier) for each scheduled event
- Pushes resulting `SoundEvent` into the state manager
- Exposes `start_scenario()`, `stop_scenario()`, `current_scenario_name` 
- Only one scenario can run at a time
- On stop: clears current state

**Does NOT:**
- Handle HTTP
- Make LLM calls
- Apply any reasoning

---

### 2. Inference Layer (`inference/`)

**Responsibility:** Accept an audio chunk (or a label hint in fake mode) and return a `SoundEvent`.

**Abstract interface (`base.py`):**
```python
class BaseClassifier(ABC):
    @abstractmethod
    def classify(self, audio_chunk: np.ndarray | None, hint: str | None = None) -> SoundEvent:
        ...
```

**FakeClassifier (`fake_classifier.py`):**
- Accepts a `hint` string (the label) and confidence override
- Returns a `SoundEvent` with that label and a realistic fake confidence
- Used by scenario engine during development

**PANNsClassifier (`panns_classifier.py`):**
- Loads CNN14 weights on init
- Accepts `audio_chunk: np.ndarray` (16kHz mono)
- Runs inference → 527-class logit vector
- Maps top AudioSet classes to SilentSense 10-class label set via lookup table
- Returns `SoundEvent` with mapped label and confidence
- Swap-in: change one line in `config.py` to activate

**Label mapping strategy (CNN14 → SilentSense):**
```python
AUDIOSET_TO_SILENTSENSE = {
    # footsteps
    "Footsteps, footfall": "footsteps",
    "Walk, footsteps": "footsteps",
    # door
    "Door": "door_open",
    "Slam": "door_open",
    "Creak": "door_open",
    "Knock": "door_knock",
    # doorbell
    "Bell": "doorbell",
    "Doorbell": "doorbell",
    # alarm
    "Alarm": "alarm_beep",
    "Beep, bleep": "alarm_beep",
    "Smoke detector, smoke alarm": "alarm_beep",
    # water
    "Water": "water_running",
    "Stream": "water_running",
    "Faucet": "water_running",
    # birds
    "Bird": "birds",
    "Bird vocalization, bird call, bird song": "birds",
    # glass
    "Glass": "glass_break",
    "Shatter": "glass_break",
    # voices
    "Shouting": "raised_voices",
    "Screaming": "raised_voices",
    # child
    "Crying, sobbing": "child_crying",
    "Baby cry, infant cry": "child_crying",
}
```

---

### 3. State Manager (`state/manager.py`)

**Responsibility:** Maintain all short-term memory of sound events.

**Stores:**
- `event_log: deque[SoundEvent]` — rolling 120s window, maxlen=200
- Per-class tracking:
  - `last_seen: float | None` — timestamp of most recent detection
  - `count_30s: int` — detections in last 30 seconds
  - `count_60s: int` — detections in last 60 seconds
  - `duration_active_s: float` — seconds since first continuous detection
  - `currently_active: bool` — true if detected in last 4 seconds
- `active_situation: SituationFlag | None` — current active flag
- `active_explanation: str | None` — most recent LLM-generated sentence
- `urgency: UrgencyLevel` — low / medium / high / critical
- `scenario_running: str | None` — name of active scenario

**Key methods:**
- `add_event(event: SoundEvent)` — appends to deque, updates per-class state
- `get_snapshot() -> AppState` — returns full immutable state snapshot
- `reset()` — clears everything, called on scenario stop
- `get_counts(label, window_s)` — count events for label in last N seconds
- `get_duration(label)` — seconds since label was first seen continuously

**Does NOT:**
- Apply any reasoning rules
- Call the LLM
- Handle HTTP

---

### 4. Reasoning Engine (`reasoning/engine.py`)

**Responsibility:** Evaluate the current `AppState` and return a `SituationFlag` if a meaningful situation is detected.

- Pure Python functions, no I/O, no async
- Called after every `add_event()` in the main pipeline
- Returns the **highest-priority** `SituationFlag` based on current state
- Compares new flag to previous flag — only signals change if different
- Does not generate explanations — only flags

**See `docs/reasoning_rules.md` for exact rule definitions.**

---

### 5. LLM Explainer (`explainer/`)

**Responsibility:** Convert a `SituationFlag` + compact state summary into one natural language sentence and a confirmed urgency level.

**Abstract interface (`base.py`):**
```python
class BaseExplainer(ABC):
    @abstractmethod
    def explain(self, flag: SituationFlag, context: ExplainerContext) -> ExplainerResponse:
        ...
```

**ExplainerContext** (what gets sent to LLM):
```python
@dataclass
class ExplainerContext:
    flag: str                    # e.g., "ARRIVAL_DETECTED"
    recent_labels: list[str]     # last 5 event labels in order
    dominant_label: str          # most frequent in last 30s
    duration_s: float | None     # relevant duration if applicable
    count: int | None            # relevant repetition count if applicable
    time_of_day: str             # "morning" / "afternoon" / "evening" / "night"
```

**System prompt (same for all providers):**
```
You are an assistive tool for deaf and hard-of-hearing users.
Given a detected sound situation, write ONE clear, calm sentence explaining what may be happening.
Rules:
- Always use hedged language: "may", "appears to", "seems like", "you may want to"
- Never make definitive claims about safety or identity
- Maximum 20 words
- Do not start with "I"
- Do not use the word "detected"
Output JSON: {"explanation": "...", "urgency": "low|medium|high|critical"}
```

**Provider selection:** Set `LLM_PROVIDER=openai|gemini|anthropic` in `.env`.

**Rate limiting:** The explainer is only called when `SituationFlag` changes. Cache the last response per flag type.

---

### 6. API Layer (`api/routes.py`)

**Responsibility:** Expose clean REST endpoints consumed by the React Native frontend.

- No business logic in routes
- Routes call: `scenario_engine`, `state_manager`, `reasoning_engine`, `explainer`
- All inputs/outputs are Pydantic models
- See `docs/api_contract.md` for full endpoint definitions

---

## Data Flow — Example: "Someone Enters" Scenario

```
t=0s    scenario starts
t=2s    FakeClassifier emits SoundEvent(label="birds", confidence=0.81)
        → state_manager.add_event()
        → reasoning_engine.evaluate() → CALM_AMBIENT
        → flag changed (None → CALM_AMBIENT)
        → explainer.explain() → "Outdoor sounds nearby, environment appears calm." / low

t=8s    FakeClassifier emits SoundEvent(label="footsteps", confidence=0.88)
        → state_manager.add_event()
        → reasoning_engine.evaluate() → CALM_AMBIENT (no sequence yet)
        → flag unchanged → no LLM call

t=11s   FakeClassifier emits SoundEvent(label="door_open", confidence=0.91)
        → state_manager.add_event()
        → reasoning_engine.evaluate() → ARRIVAL_DETECTED
        → flag changed (CALM_AMBIENT → ARRIVAL_DETECTED)
        → explainer.explain() → "Footsteps followed by a door opening — someone may have entered." / medium

t=14s   FakeClassifier emits SoundEvent(label="door_open", confidence=0.73)
        → state_manager.add_event()
        → reasoning_engine.evaluate() → ARRIVAL_DETECTED
        → flag unchanged → no LLM call
```

---

## CNN14 PANNs Integration Notes

- Weights: `Cnn14_mAP=0.431.pth` from https://github.com/qiuqiangkong/audioset_tagging_cnn
- Input: 10-second audio clip, 16kHz mono, normalized
- Output: 527-dim sigmoid vector (multi-label probabilities)
- Take top-1 class above 0.3 threshold, map via `AUDIOSET_TO_SILENTSENSE`
- If no class maps, emit `SoundEvent(label="unknown", confidence=0.0)` and skip state update
- Model loaded once on startup, stored in module-level singleton
- Inference time on GPU (24GB VRAM): ~15ms per chunk
