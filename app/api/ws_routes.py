"""WebSocket endpoint for real-time phone-mic audio streaming and inference."""

import asyncio
import contextlib
import json
import logging
import time
from collections import deque

import numpy as np
import torch
import torchaudio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.inference.panns_classifier import PANNsClassifier, PER_CLASS_THRESHOLDS, WINDOW_SAMPLES
from app.models.schemas import ExplainerContext, SoundEvent

logger = logging.getLogger(__name__)
router = APIRouter()

_PANNS_SR = 32_000


# ── Ring buffer ────────────────────────────────────────────────────────────────

class RingBuffer:
    """Accumulates 32 kHz mono float32 samples; yields overlapping WINDOW_SAMPLES windows."""

    def __init__(self, window: int, hop: int) -> None:
        """Args: window = samples per window; hop = samples to advance after each yield."""
        self._w = window
        self._h = hop
        self._buf: list[float] = []

    def push(self, samples: torch.Tensor) -> None:
        """Append a 1-D float32 tensor of any length."""
        self._buf.extend(samples.tolist())

    def pop_window(self) -> torch.Tensor | None:
        """Return the next window as a float32 tensor and advance by hop; None if not ready."""
        if len(self._buf) < self._w:
            return None
        out = torch.tensor(self._buf[: self._w], dtype=torch.float32)
        del self._buf[: self._h]
        return out


# ── Temporal smoother ─────────────────────────────────────────────────────────

class TemporalSmoother:
    """Fires a label only when it appears in ≥min_hits of the last window_n inference results.

    Returns the rising-edge set — labels that newly crossed the threshold this update.
    Labels that have already been emitted and remain active produce no further output
    until they drop below threshold and re-emerge.
    """

    def __init__(self, window_n: int, min_hits: int) -> None:
        self._window = window_n
        self._min_hits = min_hits
        self._history: deque[set[str]] = deque(maxlen=window_n)
        self._active: set[str] = set()

    def update(self, fired: set[str]) -> set[str]:
        """Record this window's fired labels; return labels newly crossing the threshold."""
        self._history.append(fired)
        if len(self._history) < self._window:
            return set()
        counts: dict[str, int] = {}
        for ws in self._history:
            for lbl in ws:
                counts[lbl] = counts.get(lbl, 0) + 1
        now_active = {lbl for lbl, n in counts.items() if n >= self._min_hits}
        newly = now_active - self._active
        self._active = now_active
        return newly


# ── Microwave / alarm_beep disambiguator ─────────────────────────────────────

class MicrowaveDisambiguator:
    """Suppresses alarm_beep detections that are actually microwave beeps.

    Logic:
    - Track microwave hits in a 5-second rolling window.
    - If microwave has 2-4 hits in that window → active burst; suppress alarm_beep.
    - Override: track the start of the current alarm_beep episode. An episode breaks
      when no alarm_beep fires for >2 s. If the current episode has been running
      ≥5 s, it's a real fire alarm — emit regardless of microwave activity.
    All other labels pass through unmodified.
    """

    _W = 5.0          # microwave rolling window (seconds)
    _MIN = 2          # min microwave hits to declare a burst
    _MAX = 4          # above this the burst logic no longer applies
    _SUSTAINED = 5.0  # alarm_beep episode length that overrides suppression
    _GAP = 2.0        # seconds of silence that ends an episode

    def __init__(self) -> None:
        self._mw: deque[float] = deque()
        self._episode_start: float | None = None
        self._last_ab: float | None = None

    def feed(self, label: str, t: float) -> bool:
        """Record detection at time t. Returns True to emit, False to suppress."""
        cutoff = t - self._W
        while self._mw and self._mw[0] < cutoff:
            self._mw.popleft()

        if label == "microwave":
            self._mw.append(t)
            return True

        if label != "alarm_beep":
            return True

        # Update alarm_beep episode tracking
        if self._last_ab is None or (t - self._last_ab) > self._GAP:
            self._episode_start = t  # new episode — reset the clock
        self._last_ab = t

        # Override: episode has been running for ≥5 s → sustained fire alarm
        if self._episode_start is not None and (t - self._episode_start) >= self._SUSTAINED:
            return True
        # Suppress if inside an active microwave burst
        if self._MIN <= len(self._mw) <= self._MAX:
            return False
        return True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_silent(w: torch.Tensor, rms_thresh: float, sf_thresh: float) -> bool:
    """Return True if the window is silence or stationary noise.

    Checks RMS first — any window with sufficient energy passes immediately,
    protecting broadband transients (glass break, etc.) from being gated.
    The spectral flatness check only applies when energy is already low.
    """
    rms = w.pow(2).mean().sqrt().item()
    if rms >= rms_thresh:
        return False  # enough energy — not silent
    mag = torch.fft.rfft(w).abs() + 1e-10
    sf = (mag.log().mean().exp() / mag.mean()).item()
    return sf > sf_thresh


def _time_of_day(ts: float) -> str:
    """Return coarse time-of-day string for explainer context."""
    h = time.localtime(ts).tm_hour
    if 5 <= h < 12:
        return "morning"
    if 12 <= h < 17:
        return "afternoon"
    if 17 <= h < 21:
        return "evening"
    return "night"


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws/audio")
async def ws_audio(websocket: WebSocket) -> None:
    """Real-time audio inference over WebSocket.

    Protocol:
      1. Client sends one JSON text header:
           {"sample_rate": 48000, "channels": 1, "encoding": "pcm_s16le"}
      2. Client sends binary frames: mono int16 little-endian PCM, ~100 ms each.
         Server resamples to 32 kHz, assembles 0.96 s windows with 50% overlap,
         applies energy gate + 2-of-3 temporal smoothing + microwave disambiguation,
         and emits detection events downstream.
      3. Server pushes JSON after each smoothed detection event (same shape as
         GET /api/v1/state/latest for frontend reuse).
      4. Text frames after the header are reserved for future control messages
         {"type": "pause"} / {"type": "resume"} — silently ignored for now.
    """
    await websocket.accept()

    classifier = websocket.app.state.classifier
    if not isinstance(classifier, PANNsClassifier):
        await websocket.send_json({"error": "Streaming requires CLASSIFIER_MODE=panns"})
        await websocket.close(code=1011)
        return

    state_manager = websocket.app.state.state_manager
    reasoning_engine = websocket.app.state.reasoning_engine
    explainer = websocket.app.state.explainer

    buf = RingBuffer(WINDOW_SAMPLES, settings.WS_HOP_SAMPLES)
    smoother = TemporalSmoother(settings.WS_SMOOTH_WINDOW, settings.WS_SMOOTH_MIN_HITS)
    disambig = MicrowaveDisambiguator()
    phone_sr = 44100  # overridden by header

    logger.info("[WS] Client connected: %s", websocket.client)

    try:
        # ── Header ──────────────────────────────────────────────────────────
        header = json.loads(await websocket.receive_text())
        phone_sr = int(header.get("sample_rate", 44100))
        logger.info("[WS] Session started — phone sample_rate=%d", phone_sr)

        # ── Audio receive loop ───────────────────────────────────────────────
        while True:
            msg = await websocket.receive()

            if msg.get("text"):
                # Control channel — reserved for future pause/resume
                logger.debug("[WS] Control message (ignored): %s", msg["text"])
                continue

            raw: bytes = msg.get("bytes") or b""
            if not raw:
                continue

            # Decode int16 LE PCM → float32 in [-1, 1]
            chunk = torch.from_numpy(
                np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
            )
            if phone_sr != _PANNS_SR:
                chunk = torchaudio.functional.resample(
                    chunk.unsqueeze(0), phone_sr, _PANNS_SR
                ).squeeze(0)

            buf.push(chunk)

            # Process every complete window available after this push
            while (window := buf.pop_window()) is not None:
                if _is_silent(
                    window,
                    settings.WS_ENERGY_RMS_THRESHOLD,
                    settings.WS_ENERGY_SF_THRESHOLD,
                ):
                    smoother.update(set())
                    continue

                scores = classifier.infer_tensor(window)
                fired = {lbl for lbl, s in scores.items() if s >= PER_CLASS_THRESHOLDS[lbl]}
                to_emit = smoother.update(fired)
                if not to_emit:
                    continue

                now = time.time()
                state_manager.decay_inactive(now)

                # Sort so microwave is fed to the disambiguator before alarm_beep
                for label in sorted(to_emit, key=lambda l: 1 if l == "alarm_beep" else 0):
                    if not disambig.feed(label, now):
                        logger.debug("[WS] alarm_beep suppressed (microwave burst)")
                        continue

                    event = SoundEvent(
                        label=label,
                        confidence=round(min(scores[label], 1.0), 4),
                        timestamp=now,
                        elapsed_s=0.0,
                    )
                    state_manager.add_event(event)
                    snapshot = state_manager.get_snapshot()
                    new_flag = reasoning_engine.evaluate(snapshot, now)

                    if new_flag != snapshot.active_situation:
                        if explainer is not None:
                            cs = snapshot.class_state.get(label)
                            ctx = ExplainerContext(
                                flag=new_flag,
                                recent_labels=[e.label for e in snapshot.event_log[-5:]],
                                dominant_label=label,
                                duration_s=cs.duration_active_s if cs else None,
                                count=cs.count_30s if cs else None,
                                time_of_day=_time_of_day(now),
                            )
                            resp = await asyncio.to_thread(explainer.explain, ctx)
                            state_manager.set_situation(new_flag, resp.explanation, resp.urgency, now)
                        else:
                            state_manager.set_situation(new_flag, None, snapshot.urgency, now)

                    snapshot = state_manager.get_snapshot()
                    await websocket.send_json({
                        "event": event.model_dump(),
                        "situation": {
                            "flag": snapshot.active_situation.value,
                            "urgency": snapshot.urgency.value,
                            "explanation": snapshot.active_explanation,
                            "flag_changed_at": snapshot.flag_changed_at,
                            "previous_flag": (
                                snapshot.previous_flag.value if snapshot.previous_flag else None
                            ),
                        },
                        "active_durations": {
                            lbl: cs.duration_active_s
                            for lbl, cs in snapshot.class_state.items()
                            if cs.currently_active
                        },
                        "counts_30s": {
                            lbl: cs.count_30s
                            for lbl, cs in snapshot.class_state.items()
                            if cs.count_30s > 0
                        },
                        "timeline": [e.model_dump() for e in snapshot.event_log[-10:]],
                    })

    except WebSocketDisconnect:
        logger.info("[WS] Client disconnected: %s", websocket.client)
    except Exception:
        logger.exception("[WS] Unhandled error — closing connection")
        with contextlib.suppress(Exception):
            await websocket.close(code=1011)
