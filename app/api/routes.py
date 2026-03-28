"""All API endpoints for SoundSense."""

import asyncio
import io
import logging
import os
import shutil
import struct
import tempfile
import time
from typing import Any

from fastapi import APIRouter, File, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.models.schemas import UrgencyLevel
from app.scenario.scenarios import SCENARIOS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

_URGENCY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


# ── Request / Response models ─────────────────────────────────────────────────

class ScenarioStartRequest(BaseModel):
    """Body for POST /scenario/start."""
    scenario: str


class DemoRunRequest(BaseModel):
    """Body for POST /demo/run."""
    scenario: str
    wait_for_completion: bool = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _error(msg: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": msg}, status_code=status)


# ── Scenario endpoints ────────────────────────────────────────────────────────

@router.post("/scenario/start")
async def scenario_start(body: ScenarioStartRequest, request: Request) -> Any:
    """Start a named scenario. Clears any existing state."""
    name = body.scenario
    if name not in SCENARIOS:
        valid = ", ".join(SCENARIOS.keys())
        return _error(f"Unknown scenario: '{name}'. Valid: [{valid}]")

    engine = request.app.state.scenario_engine
    await engine.start(name)

    scenario = SCENARIOS[name]
    return {
        "ok": True,
        "scenario": name,
        "duration_s": scenario.duration_s,
        "message": "Scenario started. Poll /state/latest every 2 seconds.",
    }


@router.post("/scenario/stop")
async def scenario_stop(request: Request) -> Any:
    """Stop the current scenario and reset all state."""
    request.app.state.scenario_engine.stop()
    return {"ok": True, "message": "Scenario stopped and state cleared."}


@router.get("/scenario/list")
async def scenario_list() -> Any:
    """List all available scenarios with metadata."""
    return {
        "scenarios": [
            {
                "name": s.name,
                "description": s.description,
                "duration_s": s.duration_s,
                "peak_urgency": s.peak_urgency,
            }
            for s in SCENARIOS.values()
        ]
    }


# ── State endpoints ───────────────────────────────────────────────────────────

@router.get("/state/latest")
async def state_latest(request: Request) -> Any:
    """Primary polling endpoint — returns full current system state."""
    state_manager = request.app.state.state_manager
    snapshot = state_manager.get_snapshot()

    now = time.time()

    # Build active_durations: only labels currently active
    active_durations: dict[str, float] = {
        label: cs.duration_active_s
        for label, cs in snapshot.class_state.items()
        if cs.currently_active
    }

    # Build counts_30s: only labels with count > 0
    counts_30s: dict[str, int] = {
        label: cs.count_30s
        for label, cs in snapshot.class_state.items()
        if cs.count_30s > 0
    }

    # Timeline: all events from event_log
    timeline = [
        {
            "label": e.label,
            "confidence": e.confidence,
            "timestamp": e.timestamp,
            "elapsed_s": e.elapsed_s,
        }
        for e in snapshot.event_log
    ]

    # raw_labels_only: last 10 event labels (for side-by-side UI panel)
    raw_labels_only = [e["label"] for e in timeline[-10:]]

    return {
        "scenario_running": snapshot.scenario_running,
        "scenario_elapsed_s": snapshot.scenario_elapsed_s,
        "situation": {
            "flag": snapshot.active_situation.value,
            "urgency": snapshot.urgency.value,
            "explanation": snapshot.active_explanation,
            "flag_changed_at": snapshot.flag_changed_at,
            "previous_flag": snapshot.previous_flag.value if snapshot.previous_flag else None,
        },
        "timeline": timeline,
        "raw_labels_only": raw_labels_only,
        "active_durations": active_durations,
        "counts_30s": counts_30s,
    }


@router.get("/state/timeline")
async def state_timeline(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    since_timestamp: float | None = Query(default=None),
) -> Any:
    """Return event timeline, optionally filtered by timestamp and limited."""
    snapshot = request.app.state.state_manager.get_snapshot()
    events = list(snapshot.event_log)

    if since_timestamp is not None:
        events = [e for e in events if e.timestamp > since_timestamp]

    events = events[-limit:]

    return {
        "events": [
            {
                "label": e.label,
                "confidence": e.confidence,
                "timestamp": e.timestamp,
                "elapsed_s": e.elapsed_s,
            }
            for e in events
        ],
        "total_count": len(events),
    }


@router.get("/state/alerts")
async def state_alerts(request: Request) -> Any:
    """Return situation changes above low urgency."""
    snapshot = request.app.state.state_manager.get_snapshot()

    low_urgency = UrgencyLevel.low.value
    alerts = [
        a for a in snapshot.alert_history
        if a.get("urgency") != low_urgency
    ]

    return {
        "alerts": [
            {
                "flag": a["flag"],
                "urgency": a["urgency"],
                "explanation": a["explanation"],
                "timestamp": a.get("timestamp"),
                "elapsed_s": a["elapsed_s"],
            }
            for a in alerts
        ]
    }


@router.post("/demo/run")
async def demo_run(body: DemoRunRequest, request: Request) -> Any:
    """Start a scenario and optionally wait for full completion.

    Designed for hackathon demos — judges can trigger one curl and get
    the complete result without polling.
    """
    name = body.scenario
    if name not in SCENARIOS:
        valid = ", ".join(SCENARIOS.keys())
        return _error(f"Unknown scenario: '{name}'. Valid: [{valid}]")

    scenario = SCENARIOS[name]
    engine = request.app.state.scenario_engine
    await engine.start(name)

    if not body.wait_for_completion:
        return {
            "ok": True,
            "scenario": name,
            "duration_s": scenario.duration_s,
            "message": "Scenario started. Poll /state/latest every 2 seconds.",
        }

    # Poll until the scenario task finishes or we hit the timeout
    deadline = time.time() + scenario.duration_s + 10
    while engine.is_running():
        if time.time() >= deadline:
            logger.warning("[SoundSense] demo/run timed out waiting for '%s'", name)
            break
        await asyncio.sleep(0.5)

    snapshot = request.app.state.state_manager.get_snapshot()

    # Determine peak flag by highest urgency across all alert history entries
    peak_flag = snapshot.active_situation.value
    peak_urgency = snapshot.urgency.value
    for alert in snapshot.alert_history:
        if _URGENCY_RANK.get(alert["urgency"], 0) > _URGENCY_RANK.get(peak_urgency, 0):
            peak_flag = alert["flag"]
            peak_urgency = alert["urgency"]

    return {
        "ok": True,
        "scenario": name,
        "duration_s": scenario.duration_s,
        "peak_flag": peak_flag,
        "peak_urgency": peak_urgency,
        "final_explanation": snapshot.active_explanation,
        "total_events": len(snapshot.event_log),
        "alerts_fired": len(snapshot.alert_history),
        "timeline_summary": [e.label for e in snapshot.event_log],
    }


@router.get("/demo/scenarios/preview")
async def demo_scenarios_preview() -> Any:
    """Return hardcoded previews of what each scenario produces.

    Used by the frontend to show judges what to expect before starting.
    """
    return {
        "previews": [
            {
                "name": "someone_enters",
                "description": "Footsteps followed by door opening",
                "expected_flag": "ARRIVAL_DETECTED",
                "expected_urgency": "medium",
                "peak_moment_s": 13,
                "why_it_matters": (
                    "Shows temporal sequence reasoning — footsteps alone are not enough, "
                    "the door event completes the inference."
                ),
            },
            {
                "name": "alarm_escalation",
                "description": "Alarm beeping repeatedly",
                "expected_flag": "ALARM_ESCALATING",
                "expected_urgency": "high",
                "peak_moment_s": 20,
                "why_it_matters": (
                    "Shows repetition tracking — single beep is noted, "
                    "three beeps triggers escalation."
                ),
            },
            {
                "name": "water_forgotten",
                "description": "Water running continuously",
                "expected_flag": "WATER_RUNNING_LONG",
                "expected_urgency": "medium",
                "peak_moment_s": 95,
                "why_it_matters": (
                    "Shows duration tracking — water running briefly is normal, "
                    "over 90 seconds suggests it was forgotten."
                ),
            },
            {
                "name": "quiet_background",
                "description": "Bird sounds only",
                "expected_flag": "CALM_AMBIENT",
                "expected_urgency": "low",
                "peak_moment_s": 7,
                "why_it_matters": (
                    "Shows the system stays calm and informative "
                    "even when nothing urgent is happening."
                ),
            },
            {
                "name": "child_alert",
                "description": "Child crying suddenly",
                "expected_flag": "CHILD_DISTRESS",
                "expected_urgency": "critical",
                "peak_moment_s": 9,
                "why_it_matters": (
                    "Shows critical urgency — child crying is always "
                    "highest priority for a deaf user."
                ),
            },
            {
                "name": "glass_break",
                "description": "Sudden sharp impact sound",
                "expected_flag": "SUDDEN_IMPACT",
                "expected_urgency": "critical",
                "peak_moment_s": 7,
                "why_it_matters": (
                    "Shows sudden event detection with 5-second recency window."
                ),
            },
        ]
    }


@router.post("/audio/classify")
async def classify_audio(request: Request, file: UploadFile = File(...)) -> Any:
    """Classify a real audio file through the active classifier and update state.

    Accepts a multipart audio upload, runs inference, updates the state manager,
    evaluates reasoning, and returns the current situation alongside the detected
    sound event.
    """
    tmp_path: str | None = None
    try:
        suffix = os.path.splitext(file.filename or "")[1] or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        audio_bytes = open(tmp_path, "rb").read()
        os.unlink(tmp_path)
        tmp_path = None

        result = _classify_and_update(request.app.state, audio_bytes)
        if not result["ok"]:
            return JSONResponse({"ok": False, "error": "Could not classify audio", "label": "unknown"}, status_code=200)
        return result

    except Exception as exc:
        logger.exception("classify_audio error: %s", exc)
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


# ── Shared audio pipeline helper ──────────────────────────────────────────────

def _wrap_pcm_as_wav(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1, sampwidth: int = 2) -> bytes:
    """Wrap raw PCM bytes in a WAV container so librosa can load them."""
    data_len = len(pcm_bytes)
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_len))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))           # chunk size
    buf.write(struct.pack("<H", 1))            # PCM format
    buf.write(struct.pack("<H", channels))
    buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", sample_rate * channels * sampwidth))  # byte rate
    buf.write(struct.pack("<H", channels * sampwidth))                 # block align
    buf.write(struct.pack("<H", sampwidth * 8))                        # bits per sample
    buf.write(b"data")
    buf.write(struct.pack("<I", data_len))
    buf.write(pcm_bytes)
    return buf.getvalue()


def _detect_audio_suffix(data: bytes) -> str:
    """Return the correct file suffix based on audio container magic bytes."""
    if data[:4] == b"RIFF":
        return ".wav"
    if data[:4] == b"OggS":
        return ".ogg"
    if data[:4] == b"\x1aE\xdf\xa3":
        return ".webm"
    # M4A / MP4 container — ftyp box at offset 4
    if data[4:8] == b"ftyp" or data[4:12] in (b"ftypM4A ", b"ftypmp42", b"ftypiso"):
        return ".m4a"
    if data[:3] == b"ID3" or (data[:2] == b"\xff\xfb"):
        return ".mp3"
    # Unknown — try m4a as that is what expo-av HIGH_QUALITY produces on iOS/Android
    return ".m4a"


def _classify_and_update(app_state, audio_bytes: bytes) -> dict:
    """Run classifier on audio bytes, update state + reasoning, return state dict.

    Detects audio container format from magic bytes and saves with the correct
    extension so librosa/ffmpeg can decode it properly. Supports WAV, M4A, OGG,
    WebM, MP3 — covering both native expo-av (M4A) and web MediaRecorder (WebM/OGG).
    """
    suffix = _detect_audio_suffix(audio_bytes)
    logger.info("[classify] detected format: %s (%d bytes)", suffix, len(audio_bytes))

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        sound_event = app_state.classifier.classify(audio_path=tmp_path)
    finally:
        os.unlink(tmp_path)

    if sound_event.label == "unknown":
        return {"ok": False, "label": "unknown"}

    now = time.time()
    app_state.state_manager.add_event(sound_event)
    app_state.state_manager.decay_inactive(now)

    snapshot = app_state.state_manager.get_snapshot()
    new_flag = app_state.reasoning_engine.evaluate(snapshot, now)

    if new_flag != snapshot.active_situation and app_state.explainer is not None:
        from app.models.schemas import ExplainerContext
        dominant = (
            max(snapshot.class_state.items(), key=lambda kv: kv[1].count_30s)[0]
            if snapshot.class_state
            else sound_event.label
        )
        hour = time.localtime(now).tm_hour
        if 5 <= hour < 12:
            tod = "morning"
        elif 12 <= hour < 17:
            tod = "afternoon"
        elif 17 <= hour < 21:
            tod = "evening"
        else:
            tod = "night"
        cs = snapshot.class_state.get(sound_event.label)
        context = ExplainerContext(
            flag=new_flag,
            recent_labels=[e.label for e in list(snapshot.event_log)[-5:]],
            dominant_label=dominant,
            duration_s=cs.duration_active_s if cs else None,
            count=cs.count_30s if cs else None,
            time_of_day=tod,
        )
        result = app_state.explainer.explain(context)
        app_state.state_manager.set_situation(new_flag, result.explanation, result.urgency, now)
    elif new_flag != snapshot.active_situation:
        app_state.state_manager.set_situation(new_flag, None, snapshot.urgency, now)

    snapshot = app_state.state_manager.get_snapshot()
    timeline = [
        {"label": e.label, "confidence": e.confidence, "timestamp": e.timestamp, "elapsed_s": e.elapsed_s}
        for e in snapshot.event_log
    ]
    return {
        "ok": True,
        "event": {"label": sound_event.label, "confidence": sound_event.confidence, "timestamp": sound_event.timestamp},
        "situation": {
            "flag": snapshot.active_situation.value,
            "urgency": snapshot.urgency.value,
            "explanation": snapshot.active_explanation,
            "flag_changed_at": snapshot.flag_changed_at,
            "previous_flag": snapshot.previous_flag.value if snapshot.previous_flag else None,
        },
        "timeline": timeline,
        "raw_labels_only": [e["label"] for e in timeline[-10:]],
    }


# ── WebSocket audio streaming ─────────────────────────────────────────────────

# 1 second of 16kHz 16-bit mono PCM = 32 000 bytes
_CHUNK_THRESHOLD = 16000 * 2


@router.websocket("/ws/audio")  # reachable at /api/v1/ws/audio
async def websocket_audio(websocket: WebSocket):
    """Receive audio chunks from frontend, classify, and push state updates back.

    Each binary message is either a complete WAV (RIFF header present) or raw
    16kHz 16-bit mono PCM. Chunks are buffered until at least 1 second of audio
    is accumulated before classification to avoid thrashing the model.
    """
    await websocket.accept()
    logger.info("[WS] client connected")
    buffer = bytearray()

    try:
        while True:
            data = await websocket.receive_bytes()
            buffer.extend(data)

            # If the message itself is a complete WAV file, classify immediately.
            is_complete_wav = data[:4] == b"RIFF"
            ready = is_complete_wav or len(buffer) >= _CHUNK_THRESHOLD

            if ready:
                audio_bytes = bytes(data) if is_complete_wav else bytes(buffer)
                buffer.clear()

                try:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None, _classify_and_update, websocket.app.state, audio_bytes
                    )
                except Exception as exc:
                    logger.exception("[WS] classify error: %s", exc)
                    result = {"ok": False, "error": str(exc)}

                await websocket.send_json(result)

    except WebSocketDisconnect:
        logger.info("[WS] client disconnected")


@router.get("/health")
async def health(request: Request) -> Any:
    """Health check — confirms backend is reachable and returns runtime info."""
    cfg = request.app.state.settings
    engine = request.app.state.scenario_engine
    return {
        "status": "ok",
        "classifier": cfg.CLASSIFIER_MODE,
        "llm_provider": cfg.LLM_PROVIDER,
        "scenario_running": engine.current_scenario_name(),
    }
