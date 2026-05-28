# SoundSense

SoundSense is an accessibility system for deaf and hard-of-hearing users that classifies environmental audio in real time, reasons over sequences and durations, and delivers prioritized natural language alerts to a mobile app. Rather than surfacing raw detection labels, SoundSense interprets patterns: footsteps followed by a door opening becomes "someone may have just arrived," three alarm beeps in thirty seconds becomes a high-urgency escalation alert. The backend runs on a local server; the Android/iOS app connects over WebSocket for live inference or falls back to REST polling when the connection drops.

---

## Repository Structure

This is a monorepo. The backend is at the root; the React Native app is in `frontend/`.

```
SoundSense/
├── app/                   backend application (FastAPI)
├── frontend/              React Native app (Expo, bare workflow)
├── docs/                  architecture, API contract, reasoning rules
├── models/                CNN14 checkpoint (.pth) — not committed
├── native_modules/        TypeScript audio capture client wrapper
├── scripts/               download weights, validate, demo scripts
├── tests/                 pytest reasoning tests, WebSocket smoke test
├── requirements.txt
├── .env.example
└── README.md
```

The backend and frontend are started independently in two terminals. They communicate over HTTP and WebSocket; the frontend has no build-time dependency on the backend.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI + uvicorn |
| Audio model | CNN14 (PANNs) via PyTorch, pretrained on AudioSet |
| Audio streaming | WebSocket, ring buffer, 50% overlapping windows at 32 kHz |
| State and reasoning | In-memory Python dataclasses, deterministic rule engine |
| LLM explanation | OpenAI gpt-4o-mini (default), Gemini Flash, Anthropic Claude Haiku |
| Mobile app | React Native 0.83 + Expo (bare workflow) |
| Navigation | React Navigation v7 |
| Config | pydantic-settings, .env file |
| Testing | pytest, websockets |

---

## Prerequisites

**Backend:**
- Python 3.11+, conda recommended
- CNN14 checkpoint: `models/Cnn14_mAP=0.431.pth` (see download instructions below)
- At least one LLM API key (OpenAI, Gemini, or Anthropic) for natural language explanations

**Frontend:**
- Node.js 18+
- Android SDK (for `npx expo run:android`) or Xcode 15+ (for iOS)
- A physical device or emulator on the same network as the backend server

---

## Quick Start

### 1. Backend

```bash
# Clone and set up environment
conda create -n soundsense python=3.11 -y
conda activate soundsense
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your LLM API key

# Download PANNs model weights
python scripts/fetch_audioset_labels.py
python scripts/download_weights.py

# Start the server (accessible from the local network)
CLASSIFIER_MODE=panns uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The server starts at `http://0.0.0.0:8000`. PANNs warm-up takes 20 to 30 seconds on first request.

To run without the model (scenario/demo mode only):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

In this mode, `CLASSIFIER_MODE` defaults to `fake` and the scenario engine emits hardcoded events. The full reasoning and LLM pipeline still runs.

### 2. Frontend

```bash
cd frontend
npm install
npx expo run:android   # or: npx expo run:ios
```

---

## Network Configuration

The frontend connects to the backend using a hardcoded host. Before running on a physical device, update this to your server's local IP address:

**File:** `frontend/src/config.js`, line 3

```js
const API_HOST = '10.250.254.2:8000';   // change to your server's IP
```

Both `BASE_URL` (REST) and `WS_URL` (WebSocket) are derived from this single value.

**Why `--host 0.0.0.0` matters:** binding to `127.0.0.1` accepts connections from the same machine only. Binding to `0.0.0.0` accepts connections from any network interface, which is required for a physical phone to reach the backend over Wi-Fi. For production deployment, replace the IP with your server's domain name and remove `--reload`.

---

## Sound Classes

All ten classes feed directly into the reasoning engine. Each label maps to one or more situation flags.

| Label | Description | Situation flags triggered |
|---|---|---|
| `footsteps` | Walking sounds nearby | `ARRIVAL_DETECTED`, `FOOTSTEPS_ONLY` |
| `door_open` | Door opening or closing | `ARRIVAL_DETECTED` |
| `door_knock` | Knocking on a door | `KNOCK_OR_BELL` |
| `doorbell` | Bell or chime at door | `KNOCK_OR_BELL` |
| `alarm_beep` | Electronic beep or alarm | `ALARM_ESCALATING` (3+ in 30s), `ALARM_SINGLE` (1-2 in 30s) |
| `water_running` | Tap, shower, or pipe | `WATER_RUNNING_LONG` (>90s), `WATER_RUNNING_BRIEF` (20-90s) |
| `birds` | Outdoor ambient birdsong | `CALM_AMBIENT` |
| `glass_break` | Sudden shattering sound | `SUDDEN_IMPACT` |
| `raised_voices` | Shouting or argument | `RAISED_VOICES_DETECTED` |
| `child_crying` | Infant or child distress | `CHILD_DISTRESS` |

Situation flags are evaluated in priority order: `SUDDEN_IMPACT` and `CHILD_DISTRESS` are always critical; `NONE` is the baseline when no rule matches.

---

## API Endpoints

### REST

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Root health check |
| `GET` | `/api/v1/health` | Health check with classifier and LLM provider info |
| `GET` | `/api/v1/scenario/list` | List all available scenarios with metadata |
| `POST` | `/api/v1/scenario/start` | Start a named scenario |
| `POST` | `/api/v1/scenario/stop` | Stop current scenario and reset state |
| `GET` | `/api/v1/state/latest` | Primary polling endpoint, full system state |
| `GET` | `/api/v1/state/timeline` | Event timeline with optional `limit` and `since_timestamp` |
| `GET` | `/api/v1/state/alerts` | Situation changes above low urgency |
| `POST` | `/api/v1/audio/classify` | Classify an uploaded audio file (multipart) |
| `POST` | `/api/v1/demo/run` | Start a scenario and optionally wait for completion |
| `GET` | `/api/v1/demo/scenarios/preview` | Metadata preview for all scenarios |

### WebSocket

**Endpoint:** `ws://<host>/ws/audio`

Requires `CLASSIFIER_MODE=panns`. The connection follows a two-phase protocol:

1. Client sends one JSON text frame as a session header:
   ```json
   {"sample_rate": 48000, "channels": 1, "encoding": "pcm_s16le"}
   ```

2. Client sends binary frames of mono int16 little-endian PCM at approximately 100 ms per chunk (the native module sends at 48 kHz; the server resamples to 32 kHz internally).

3. Server pushes a JSON frame after each smoothed detection event. The shape is identical to `GET /api/v1/state/latest` with an additional `event` key containing the triggering detection.

The pipeline applies an energy gate, 2-of-3 temporal smoothing, and a microwave disambiguator before emitting detections to the state manager.

### Available Scenarios

| Scenario | Peak urgency | Duration |
|---|---|---|
| `someone_enters` | medium | 45s |
| `alarm_escalation` | high | 35s |
| `water_forgotten` | medium | 120s |
| `quiet_background` | low | 30s |
| `child_alert` | critical | 20s |
| `glass_break` | critical | 15s |

Start a scenario:

```bash
curl -X POST http://localhost:8000/api/v1/scenario/start \
  -H "Content-Type: application/json" \
  -d '{"scenario": "someone_enters"}'
```

Poll state:

```bash
curl http://localhost:8000/api/v1/state/latest
```

---

## Environment Variables

All configuration is via `.env` (copy from `.env.example`).

| Variable | Default | Description |
|---|---|---|
| `CLASSIFIER_MODE` | `fake` | `fake` for scenario/demo mode, `panns` for CNN14 inference |
| `PANNS_CHECKPOINT` | `models/Cnn14_mAP=0.431.pth` | Path to CNN14 weights file |
| `LLM_PROVIDER` | `openai` | LLM provider: `openai`, `gemini`, or `anthropic` |
| `LLM_MODEL` | `gpt-4o-mini` | Model name for OpenAI |
| `OPENAI_API_KEY` | `""` | OpenAI API key |
| `GEMINI_API_KEY` | `""` | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Gemini model name |
| `ANTHROPIC_API_KEY` | `""` | Anthropic API key |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` | Anthropic model name |
| `LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING` |
| `CORS_ORIGINS` | localhost list | Set to `["*"]` to allow all origins |
| `WS_HOP_SAMPLES` | `15360` | Ring buffer hop size in samples (50% overlap at 32 kHz) |
| `WS_ENERGY_RMS_THRESHOLD` | `0.001` | RMS below this triggers silence check |
| `WS_ENERGY_SF_THRESHOLD` | `0.85` | Spectral flatness above this gates the window as silent |
| `WS_SMOOTH_WINDOW` | `3` | Number of consecutive windows for temporal smoothing |
| `WS_SMOOTH_MIN_HITS` | `2` | Minimum hits in window to emit a detection |

If no LLM API key is set, the server starts without an explainer. Reasoning flags and urgency levels are still produced; explanations fall back to a static string.

---

## Project Structure

```
app/
├── main.py                    FastAPI entry point, lifespan startup
├── config.py                  pydantic-settings config
├── models/schemas.py          all Pydantic models and enums
├── api/
│   ├── routes.py              REST endpoints
│   └── ws_routes.py           WebSocket endpoint, ring buffer, smoother, disambiguator
├── inference/
│   ├── base.py                abstract classifier interface
│   ├── panns_classifier.py    CNN14 inference, per-class thresholds, infer_tensor
│   ├── fake_classifier.py     hardcoded label emitter for scenario mode
│   └── yamnet_classifier.py   YAMNet alternative (CLASSIFIER_MODE=yamnet)
├── state/manager.py           event deque, duration tracking, snapshot
├── reasoning/engine.py        deterministic rule engine, 11 priority-ordered rules
├── explainer/
│   ├── base.py                abstract LLM interface
│   ├── openai_explainer.py
│   ├── gemini_explainer.py
│   └── anthropic_explainer.py
└── scenario/
    ├── engine.py              async scenario runner
    └── scenarios.py           six predefined scenario definitions

frontend/
├── src/config.js              single source of truth for backend host
├── src/hooks/useAudioStream.js  mic capture + WebSocket lifecycle hook
├── src/services/AudioWebSocket.js  WebSocket client with reconnect logic
├── src/services/MicrophoneStream.js  native audio capture wrapper
├── src/screens/HomeScreen.js  main alert feed, WebSocket and REST integration
├── src/screens/LoginScreen.js
├── src/screens/OnboardingScreen.js
└── src/navigation/AppNavigator.js

tests/
├── test_reasoning.py          13 pytest unit tests for the rule engine
├── ws_smoke_test.py           end-to-end WebSocket test against real audio files
└── ws_diag.py                 window-by-window PANNs diagnostic tool
```

---

## Testing

### Reasoning engine unit tests

```bash
pytest tests/test_reasoning.py -v
```

Covers 13 rule cases including arrival detection ordering, alarm escalation thresholds, water duration boundaries, and expiry windows.

### WebSocket end-to-end smoke test

Requires `CLASSIFIER_MODE=panns` and the CNN14 checkpoint. Starts a server subprocess, streams real audio files as 100 ms int16 PCM frames, and validates that the correct labels, situation flags, and JSON shapes are returned.

```bash
CLASSIFIER_MODE=panns python tests/ws_smoke_test.py
```

Test cases: `test_audio/smoke-alarm.mp3` (expects `alarm_beep`, `ALARM_*`) and `test_audio/baby-crying-high-pitch.mp3` (expects `child_crying`, `CHILD_DISTRESS`).

### PANNs pipeline diagnostic

Prints window-by-window inference scores, gate decisions, and smoother state for a given audio file. Useful for tuning thresholds or diagnosing missed detections.

```bash
python tests/ws_diag.py test_audio/smoke-alarm.mp3
```

### Full demo validation

Runs health check, scenario list check, and three end-to-end scenario validations against a running server:

```bash
PYTHONPATH=. python scripts/validate_demo.py
```

---

## LLM Provider Switching

Set `LLM_PROVIDER` and the matching API key in `.env`:

```bash
# OpenAI (default)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Google Gemini
LLM_PROVIDER=gemini
GEMINI_API_KEY=...

# Anthropic Claude
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=...
```

The LLM is called only when the active situation flag changes, not on every audio chunk or event.
