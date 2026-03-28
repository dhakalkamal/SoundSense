"""All API endpoints for SoundSense."""

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, Query, Request
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
