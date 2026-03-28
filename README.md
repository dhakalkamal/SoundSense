# SoundSense Backend

## What This Is

SoundSense is a stateful sound reasoning backend for deaf and hard-of-hearing users. It classifies environmental audio using CNN14 PANNs, maintains short-term event memory, applies deterministic rule-based temporal reasoning, and generates natural language situation explanations via OpenAI. It is not just a classifier — it reasons over sequences, durations, and repetitions to understand *what is happening*, not just *what sound was heard*.

---

## Quick Start

```bash
conda activate genai
pip install -r requirements.txt
cp .env.example .env
# Add your OPENAI_API_KEY to .env

python scripts/fetch_audioset_labels.py
python scripts/download_weights.py

uvicorn app.main:app --reload
```

The server starts at `http://localhost:8000`. With `CLASSIFIER_MODE=fake` (default), no weights file is needed — the scenario engine emits hardcoded events and the full reasoning + LLM pipeline still runs.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | `""` | OpenAI API key (required for explanations with OpenAI) |
| `LLM_PROVIDER` | `openai` | LLM provider: `openai`, `gemini`, or `anthropic` |
| `LLM_MODEL` | `gpt-4o-mini` | OpenAI model name |
| `GEMINI_API_KEY` | `""` | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Gemini model name |
| `ANTHROPIC_API_KEY` | `""` | Anthropic API key |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` | Anthropic model name |
| `CLASSIFIER_MODE` | `fake` | `fake` for scenario demo, `panns` for real CNN14 audio |
| `PANNS_CHECKPOINT` | `models/Cnn14_mAP=0.431.pth` | Path to CNN14 weights file |
| `LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING` |
| `CORS_ORIGINS` | *(localhost list)* | Allowed CORS origins, set to `["*"]` to allow all |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Root health check |
| `GET` | `/api/v1/health` | Full health check with classifier and LLM provider info |
| `GET` | `/api/v1/scenario/list` | List all available scenarios with metadata |
| `POST` | `/api/v1/scenario/start` | Start a named scenario |
| `POST` | `/api/v1/scenario/stop` | Stop current scenario and reset state |
| `GET` | `/api/v1/state/latest` | Primary polling endpoint — full system state |
| `GET` | `/api/v1/state/timeline` | Event timeline with optional `limit` and `since_timestamp` |
| `GET` | `/api/v1/state/alerts` | Situation changes above low urgency |
| `POST` | `/api/v1/demo/run` | Start scenario and optionally wait for full completion |
| `GET` | `/api/v1/demo/scenarios/preview` | Hardcoded preview of what each scenario produces |

---

## Running Scenarios

**Start a scenario:**
```bash
curl -X POST http://localhost:8000/api/v1/scenario/start \
  -H "Content-Type: application/json" \
  -d '{"scenario": "someone_enters"}'
```

**Poll state every 2 seconds:**
```bash
curl http://localhost:8000/api/v1/state/latest
```

**Run full demo scenario and get complete result in one call:**
```bash
curl -X POST http://localhost:8000/api/v1/demo/run \
  -H "Content-Type: application/json" \
  -d '{"scenario": "someone_enters", "wait_for_completion": true}'
```

---

## Validate Everything Works

```bash
PYTHONPATH=. python scripts/validate_demo.py
```

Runs health check, scenario list check, and three full end-to-end scenario validations against the live server. Prints a pass/fail summary.

---

## Sound Classes

| Label | Description |
|---|---|
| `footsteps` | Walking sounds nearby |
| `door_open` | Door opening or slamming |
| `door_knock` | Knocking on a door |
| `doorbell` | Bell or chime at door |
| `alarm_beep` | Electronic beep or alarm |
| `water_running` | Tap, shower, or pipe sound |
| `birds` | Outdoor ambient birdsong |
| `glass_break` | Sudden shattering sound |
| `raised_voices` | Shouting or argument |
| `child_crying` | Infant or child distress |

---

## Architecture

The scenario engine emits timed `SoundEvent` objects (fake labels in demo mode, CNN14 inference in production). Events flow into the state manager, which maintains a rolling 200-event deque and per-label duration and activity tracking. The reasoning engine applies deterministic priority-ordered rules over the state snapshot to produce a `SituationFlag`. When the flag changes, the LLM explainer converts it into a single hedged natural language sentence with an urgency level. The API assembles and serves this state on every poll.

See `docs/architecture.md` for full module breakdown and data flow diagrams.

---

## LLM Provider Switching

Set `LLM_PROVIDER` and the corresponding API key in `.env`:

```bash
# OpenAI (default, recommended)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Google Gemini
LLM_PROVIDER=gemini
GEMINI_API_KEY=...

# Anthropic Claude
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=...
```

If no API key is found, the server starts without an explainer — scenarios still run and reasoning flags are still emitted, but explanations fall back to `"Sound activity noted nearby."`.
