# CLAUDE.md — SilentSense Backend

## What This Project Is

SilentSense is a backend + ML system for an accessibility tool targeting deaf and hard-of-hearing users.
It classifies sound events from audio, maintains short-term event memory, applies rule-based temporal
reasoning, and generates contextual natural language explanations with urgency levels.

This is a hackathon MVP. Every decision should optimize for demo reliability and code clarity.

---

## What You Are Building (Backend Only)

You are responsible for:
- Sound inference pipeline (CNN14 PANNs pretrained model)
- Event state manager (short-term memory of sound events)
- Reasoning engine (deterministic rule-based logic)
- LLM explanation layer (API-agnostic, default OpenAI)
- Scenario playback engine (simulated timed audio events)
- FastAPI REST API (consumed by React Native frontend)

You are NOT building:
- Any React Native or frontend code
- Real-time microphone streaming
- A training pipeline or custom model
- A database or persistent storage
- Authentication or user management
- Speech-to-text or voice transcription

---

## Architecture Overview

```
scenario_engine → audio_inference → state_manager → reasoning_engine → llm_explainer → API response
```

See `docs/architecture.md` for full module breakdown.

---

## Sound Classes (Fixed — Do Not Expand Without Instruction)

| Label | Notes |
|---|---|
| `footsteps` | Walking sounds |
| `door_open` | Door opening sound |
| `door_knock` | Knocking on door |
| `doorbell` | Bell or chime at door |
| `alarm_beep` | Electronic beep / alarm |
| `water_running` | Tap, shower, pipe |
| `birds` | Outdoor ambient birdsong |
| `glass_break` | Sudden shattering |
| `raised_voices` | Shouting or argument |
| `child_crying` | Infant or child distress |

---

## Core Design Principles

1. **Rules-first, LLM-second.** The reasoning engine uses deterministic Python rules to detect situations
   (e.g., ARRIVAL_DETECTED, ALARM_ESCALATING). The LLM only converts a situation flag into a sentence.
   The LLM does NOT make inferences. It only generates language.

2. **Fake labels before real model.** The scenario engine emits fake SoundEvent objects with hardcoded
   labels and confidence scores. CNN14 inference is swapped in later without changing any downstream code.
   All modules below the inference layer must work identically with fake or real labels.

3. **State is in-memory only.** No database. No Redis. A Python dataclass with a deque. Reset on restart.
   This is a hackathon.

4. **LLM calls are rate-limited.** Only call the LLM when a situation flag CHANGES state. Not on every
   audio chunk. Not on every event. Only on state transitions.

5. **API is frontend-stable.** The response shape defined in `docs/api_contract.md` must not change
   without explicit instruction. The frontend team depends on it.

6. **LLM provider is abstracted.** The LLM client must be behind an interface so OpenAI, Gemini, and
   Anthropic can be swapped by changing one config value. Default: OpenAI gpt-4o-mini.

---

## Tech Stack

| Component | Choice |
|---|---|
| Language | Python 3.11+ |
| Framework | FastAPI |
| Audio model | CNN14 (PANNs) via PyTorch |
| LLM (default) | OpenAI gpt-4o-mini |
| LLM (benchmark) | Gemini Flash, Anthropic Claude Haiku |
| Event memory | Python dataclass + collections.deque |
| Scenario engine | Python async loop with asyncio.sleep |
| Config | pydantic-settings + .env file |
| Testing | pytest |

---

## Folder Structure

```
silentsense/
├── CLAUDE.md                  ← this file
├── docs/
│   ├── architecture.md
│   ├── api_contract.md
│   └── reasoning_rules.md
├── app/
│   ├── main.py                ← FastAPI app entry point
│   ├── config.py              ← pydantic-settings config
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py          ← all API endpoints
│   ├── inference/
│   │   ├── __init__.py
│   │   ├── base.py            ← abstract classifier interface
│   │   ├── fake_classifier.py ← returns hardcoded labels (used first)
│   │   └── panns_classifier.py← CNN14 real inference (swapped in later)
│   ├── state/
│   │   ├── __init__.py
│   │   └── manager.py         ← event memory, deque, duration tracking
│   ├── reasoning/
│   │   ├── __init__.py
│   │   └── engine.py          ← deterministic rule engine, returns SituationFlags
│   ├── explainer/
│   │   ├── __init__.py
│   │   ├── base.py            ← abstract LLM interface
│   │   ├── openai_explainer.py
│   │   ├── gemini_explainer.py
│   │   └── anthropic_explainer.py
│   ├── scenario/
│   │   ├── __init__.py
│   │   ├── engine.py          ← async scenario runner
│   │   └── scenarios.py       ← predefined scenario definitions
│   └── models/
│       ├── __init__.py
│       └── schemas.py         ← all Pydantic models (SoundEvent, AppState, APIResponse)
├── tests/
│   ├── test_state.py
│   ├── test_reasoning.py
│   └── test_scenarios.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## Implementation Order (Follow This Exactly)

1. `models/schemas.py` — define all data models first
2. `state/manager.py` — event memory, no inference needed
3. `reasoning/engine.py` — rules only, test with fake events
4. `inference/fake_classifier.py` — hardcoded label emitter
5. `scenario/engine.py` + `scenario/scenarios.py` — scenario playback
6. `explainer/` — LLM interface + OpenAI implementation
7. `api/routes.py` + `main.py` — wire everything into FastAPI
8. `inference/panns_classifier.py` — swap in real CNN14
9. Tests — reasoning rules and state manager

---

## What "Done" Looks Like for Demo

A POST to `/scenario/start` with `{"scenario": "someone_enters"}` begins a timed sequence of sound
events. The frontend polls `/state/latest` every 2 seconds. It receives urgency level, contextual
explanation, active situation flag, and full event timeline. The demo shows the system reasoning over
time — not just detecting labels.

---

## Constraints and Rules for Claude Code

- Do not add dependencies not listed in requirements.txt without flagging it
- Do not use global mutable state outside of `state/manager.py`
- Do not call the LLM more than once per situation flag change
- Do not add streaming, websockets, or real-time audio unless explicitly instructed
- Do not add a database layer
- Keep every module under 150 lines where possible
- Every public function must have a docstring
- Pydantic models for all API inputs and outputs
- All config via environment variables, never hardcoded
