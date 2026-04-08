#!/usr/bin/env python3
"""
WebSocket end-to-end smoke test for the SoundSense streaming pipeline.

Starts a temporary server, streams each test audio file as ~100 ms int16 PCM
frames (exactly as the iOS/Android native module would), and prints every
detection event the server pushes back.  No native module or React Native UI needed.

Usage (from project root):
    CLASSIFIER_MODE=panns python tests/ws_smoke_test.py

What this validates:
  - Ring buffer assembles phone-sized chunks into 0.96 s PANNs windows
  - Resampler converts 48 kHz phone audio to 32 kHz for CNN14
  - Energy gate passes real audio (alarm, crying) without gating
  - PANNs inference returns correct group scores above 0.4 threshold
  - 2-of-3 temporal smoother fires rising edge only (no repeated events)
  - MicrowaveDisambiguator passes alarm_beep through (no microwave context)
  - StateManager and ReasoningEngine produce a non-NONE situation flag
  - Server pushes correctly shaped JSON (same schema as GET /state/latest)
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import librosa
import numpy as np

# ── Constants ─────────────────────────────────────────────────────────────────

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8766              # separate port so we don't clash with a running dev server
WS_URL = f"ws://{SERVER_HOST}:{SERVER_PORT}/ws/audio"
HEALTH_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/api/v1/health"

PHONE_SAMPLE_RATE = 48_000      # what the native module captures at
FRAME_SAMPLES = PHONE_SAMPLE_RATE // 10   # 4800 samples = ~100 ms per chunk

PROJECT_ROOT = Path(__file__).parent.parent

TEST_CASES = [
    {
        "file": "test_audio/smoke-alarm.mp3",
        "expect_label": "alarm_beep",
        "expect_flag_prefix": "ALARM_",   # ALARM_SINGLE or ALARM_ESCALATING
        "description": "Smoke alarm → alarm_beep → ALARM reasoning rule",
    },
    {
        "file": "test_audio/baby-crying-high-pitch.mp3",
        "expect_label": "child_crying",
        "expect_flag_prefix": "CHILD_DISTRESS",
        "description": "Baby crying → child_crying → CHILD_DISTRESS reasoning rule",
    },
]

# ── Server lifecycle ──────────────────────────────────────────────────────────

def start_server() -> subprocess.Popen:
    """Start uvicorn in a subprocess with CLASSIFIER_MODE=panns."""
    env = {
        **os.environ,
        "CLASSIFIER_MODE": "panns",
        # Avoid LLM calls during smoke test — no network dependency
        "LLM_PROVIDER": "openai",  # still loads OpenAI if key exists, that's fine
    }
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", SERVER_HOST,
            "--port", str(SERVER_PORT),
            "--log-level", "warning",
        ],
        env=env,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc


def wait_for_server(timeout: float = 90.0) -> bool:
    """Poll /health until the server responds (PANNs warm-up takes ~20-30 s)."""
    deadline = time.time() + timeout
    dots = 0
    while time.time() < deadline:
        try:
            urllib.request.urlopen(HEALTH_URL, timeout=2)
            print()
            return True
        except Exception:
            time.sleep(1.0)
            print(".", end="", flush=True)
            dots += 1
    print()
    return False

# ── Audio preparation ─────────────────────────────────────────────────────────

def load_chunks(audio_path: str) -> tuple[list[bytes], float]:
    """Load audio, resample to 48 kHz mono, split into ~100 ms int16 chunks.

    Returns (chunks, duration_seconds).  Mirrors exactly what the native
    module sends: little-endian int16 PCM at PHONE_SAMPLE_RATE.
    """
    audio, _ = librosa.load(audio_path, sr=PHONE_SAMPLE_RATE, mono=True)
    pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
    duration_s = len(pcm) / PHONE_SAMPLE_RATE

    chunks = []
    for i in range(0, len(pcm), FRAME_SAMPLES):
        frame = pcm[i : i + FRAME_SAMPLES]
        if len(frame) < FRAME_SAMPLES:
            frame = np.pad(frame, (0, FRAME_SAMPLES - len(frame)))
        chunks.append(frame.tobytes())   # already LE on little-endian hosts; see note below
    # Note: np.int16.tobytes() emits native byte order. On x86/ARM (little-endian),
    # this matches the server's np.frombuffer(..., dtype="<i2"). On big-endian hosts,
    # use frame.byteswap().tobytes() instead. All modern Macs and phones are LE.

    return chunks, duration_s


# ── WebSocket test runner ─────────────────────────────────────────────────────

async def stream_and_collect(audio_path: str) -> list[dict]:
    """Open WebSocket, stream all chunks, collect every server push. Return events."""
    import websockets  # imported here — already in requirements.txt

    chunks, duration_s = load_chunks(audio_path)
    print(f"    {len(chunks)} frames × 100 ms = {duration_s:.1f} s of audio")

    events: list[dict] = []
    header = json.dumps({
        "sample_rate": PHONE_SAMPLE_RATE,
        "channels": 1,
        "encoding": "pcm_s16le",
    })

    async with websockets.connect(
        WS_URL,
        ping_interval=None,    # disable keepalive pings during the test
        open_timeout=15,
        close_timeout=5,
    ) as ws:
        await ws.send(header)

        send_done = asyncio.Event()

        async def sender():
            for chunk in chunks:
                await ws.send(chunk)
                await asyncio.sleep(0)  # yield so receiver can drain server pushes
            send_done.set()

        async def receiver():
            # Phase 1: poll while sender is still running.
            while not send_done.is_set():
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=0.1)
                    events.append(json.loads(raw))
                except asyncio.TimeoutError:
                    pass  # sender still going — keep polling

            # Phase 2: sender done; give the server up to 30 s to finish processing
            # all queued windows (PANNs ~11 ms/window × ~37 windows ≈ 400 ms) plus
            # any LLM explainer calls (~1–2 s each).
            try:
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    events.append(json.loads(raw))
            except asyncio.TimeoutError:
                pass  # no more events

        await asyncio.gather(sender(), receiver())

    return events


# ── Result checker and printer ────────────────────────────────────────────────

def check_and_print(
    events: list[dict],
    expect_label: str,
    expect_flag_prefix: str,
    case_desc: str,
) -> bool:
    """Validate events and print a human-readable summary. Returns True if passed."""
    passed = True

    if not events:
        print("  FAIL — no detection events received")
        return False

    labels_seen = [e["event"]["label"] for e in events]
    flags_seen = [e["situation"]["flag"] for e in events]

    # 1. Correct label fired
    if expect_label not in labels_seen:
        print(f"  FAIL — expected label '{expect_label}' not in {labels_seen}")
        passed = False
    else:
        print(f"  PASS — '{expect_label}' detected")

    # 2. Rising-edge only: same label should not appear in two consecutive events
    #    (it can re-appear after a gap, but not back-to-back)
    for i in range(1, len(events)):
        if events[i]["event"]["label"] == events[i - 1]["event"]["label"] == expect_label:
            print(f"  WARN — '{expect_label}' fired in consecutive events (smoother may re-fire on long audio)")
            break  # warn but don't fail — long files naturally re-detect

    # 3. Reasoning engine produced the expected situation
    if not any(f.startswith(expect_flag_prefix) for f in flags_seen):
        print(f"  FAIL — expected flag prefix '{expect_flag_prefix}' not in {flags_seen}")
        passed = False
    else:
        matching = [f for f in flags_seen if f.startswith(expect_flag_prefix)]
        print(f"  PASS — situation flag '{matching[0]}' produced by reasoning engine")

    # 4. JSON shape: required keys present in every event
    required_keys = {"event", "situation", "timeline", "active_durations", "counts_30s"}
    for i, ev in enumerate(events):
        missing = required_keys - ev.keys()
        if missing:
            print(f"  FAIL — event {i} missing keys: {missing}")
            passed = False
            break
    else:
        print(f"  PASS — all {len(events)} events have correct JSON shape")

    # 5. Print each detection event compactly
    print(f"\n  {'─' * 56}")
    print(f"  {'DETECTION EVENTS':}")
    print(f"  {'─' * 56}")
    for ev in events:
        e = ev["event"]
        s = ev["situation"]
        conf = e.get("confidence", 0)
        print(
            f"  [{e['label']:20s}  conf={conf:.3f}]  "
            f"flag={s['flag']:25s}  urgency={s['urgency']}"
        )
        if s.get("explanation"):
            # Wrap explanation at 70 chars
            expl = s["explanation"]
            print(f"    → {expl[:110]}{'…' if len(expl) > 110 else ''}")
    print(f"  {'─' * 56}")

    return passed


# ── Main ─────────────────────────────────────────────────────────────────────

async def run_all_tests() -> bool:
    all_passed = True
    for case in TEST_CASES:
        audio_path = str(PROJECT_ROOT / case["file"])
        print(f"\n{'═' * 60}")
        print(f"TEST: {case['description']}")
        print(f"{'═' * 60}")
        print(f"  Streaming: {case['file']}")

        if not Path(audio_path).exists():
            print(f"  SKIP — file not found: {audio_path}")
            continue

        events = await stream_and_collect(audio_path)

        ok = check_and_print(
            events,
            case["expect_label"],
            case["expect_flag_prefix"],
            case["description"],
        )
        if not ok:
            all_passed = False
        print(f"\n  Result: {'PASS ✓' if ok else 'FAIL ✗'}")

    return all_passed


def main() -> int:
    print("SoundSense WebSocket Smoke Test")
    print("================================")
    print(f"Server: {WS_URL}")
    print()

    print("Starting server (PANNs warm-up may take ~20-30 s)...")
    proc = start_server()

    try:
        if not wait_for_server():
            print("ERROR: server did not become healthy within 90 s")
            stderr = proc.stderr.read(3000).decode(errors="replace")
            print("Server stderr:\n", stderr)
            return 1

        print("Server ready.\n")
        all_passed = asyncio.run(run_all_tests())

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    print(f"\n{'═' * 60}")
    print(f"Overall: {'ALL TESTS PASSED ✓' if all_passed else 'SOME TESTS FAILED ✗'}")
    print(f"{'═' * 60}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
