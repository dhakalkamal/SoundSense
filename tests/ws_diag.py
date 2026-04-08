#!/usr/bin/env python3
"""
Standalone window-by-window PANNs diagnostic.

Mirrors the exact ws_routes.py pipeline (resample → ring buffer → energy gate →
infer_tensor → threshold compare → smoother) and prints raw scores for every
window so we can see where detections are blocked.

Usage (from project root):
    python tests/ws_diag.py test_audio/smoke-alarm.mp3
    python tests/ws_diag.py test_audio/baby-crying-high-pitch.mp3
"""

import sys
from pathlib import Path

# Allow running from project root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

import librosa
import numpy as np
import torch
import torchaudio

from app.config import settings
from app.inference.panns_classifier import (
    PANNsClassifier,
    PER_CLASS_THRESHOLDS,
    WINDOW_SAMPLES,
)

# ── Constants (must match ws_routes.py) ───────────────────────────────────────
_PANNS_SR = 32_000
_PHONE_SR = 48_000   # what the native module sends; what load_chunks() resamples to

# ── Energy gate (copied verbatim from ws_routes.py) ───────────────────────────
def _is_silent(w: torch.Tensor, rms_thresh: float, sf_thresh: float) -> bool:
    rms = w.pow(2).mean().sqrt().item()
    if rms >= rms_thresh:
        return False
    mag = torch.fft.rfft(w).abs() + 1e-10
    sf = (mag.log().mean().exp() / mag.mean()).item()
    return sf > sf_thresh


def run(audio_path: str) -> None:
    print(f"\n{'═' * 70}")
    print(f"FILE: {audio_path}")
    print(f"{'═' * 70}")
    print(f"Settings: RMS_THRESH={settings.WS_ENERGY_RMS_THRESHOLD}  "
          f"SF_THRESH={settings.WS_ENERGY_SF_THRESHOLD}  "
          f"SMOOTH_WINDOW={settings.WS_SMOOTH_WINDOW}  "
          f"SMOOTH_MIN_HITS={settings.WS_SMOOTH_MIN_HITS}")
    print(f"PER_CLASS_THRESHOLDS: {PER_CLASS_THRESHOLDS}")
    print(f"WINDOW_SAMPLES={WINDOW_SAMPLES}  HOP={settings.WS_HOP_SAMPLES}")
    print()

    # Load audio at phone sample rate (simulates native module)
    print("Loading audio at 48 kHz (phone rate)...")
    audio_48k, _ = librosa.load(audio_path, sr=_PHONE_SR, mono=True)
    duration_s = len(audio_48k) / _PHONE_SR
    print(f"Duration: {duration_s:.2f} s  ({len(audio_48k)} samples @ 48 kHz)")

    # Resample to 32 kHz (what the server does per chunk)
    audio_tensor_48k = torch.from_numpy(audio_48k.astype(np.float32))
    audio_32k = torchaudio.functional.resample(
        audio_tensor_48k.unsqueeze(0), _PHONE_SR, _PANNS_SR
    ).squeeze(0)
    print(f"After resample: {len(audio_32k)} samples @ 32 kHz\n")

    # Load model
    ckpt = str(Path(__file__).parent.parent / settings.PANNS_CHECKPOINT)
    print(f"Loading PANNs checkpoint: {ckpt}")
    clf = PANNsClassifier(ckpt)
    print()

    # Slice into overlapping windows (same as RingBuffer with 50% hop)
    win = WINDOW_SAMPLES
    hop = settings.WS_HOP_SAMPLES
    total_samples = len(audio_32k)

    w_idx = 0
    pos = 0
    gated = 0
    below_thresh = 0
    fired_windows = 0

    # Track smoother state to replicate 2-of-3 logic
    from collections import deque
    history: deque[set] = deque(maxlen=settings.WS_SMOOTH_WINDOW)
    active: set = set()

    print(f"{'WIN':>4}  {'RMS':>8}  {'SF':>6}  {'GATED':>6}  "
          f"{'alarm_beep':>10}  {'child_crying':>12}  {'fired_raw':>30}  {'smoothed':>30}")
    print("─" * 120)

    while pos + win <= total_samples:
        window = audio_32k[pos : pos + win]
        pos += hop
        w_idx += 1

        rms = window.pow(2).mean().sqrt().item()
        # Compute spectral flatness regardless (for display)
        mag = torch.fft.rfft(window).abs() + 1e-10
        sf = (mag.log().mean().exp() / mag.mean()).item()

        gated_flag = _is_silent(window, settings.WS_ENERGY_RMS_THRESHOLD, settings.WS_ENERGY_SF_THRESHOLD)

        if gated_flag:
            gated += 1
            history.append(set())
            print(f"{w_idx:>4}  {rms:>8.5f}  {sf:>6.3f}  {'GATED':>6}  "
                  f"{'—':>10}  {'—':>12}  {'':>30}  {'':>30}")
            continue

        # Run inference
        scores = clf.infer_tensor(window)
        fired_raw = {lbl for lbl, s in scores.items() if s >= PER_CLASS_THRESHOLDS[lbl]}

        if fired_raw:
            fired_windows += 1
        else:
            below_thresh += 1

        # Smoother
        history.append(fired_raw)
        newly: set = set()
        if len(history) >= settings.WS_SMOOTH_WINDOW:
            counts: dict[str, int] = {}
            for ws in history:
                for lbl in ws:
                    counts[lbl] = counts.get(lbl, 0) + 1
            now_active = {lbl for lbl, n in counts.items() if n >= settings.WS_SMOOTH_MIN_HITS}
            newly = now_active - active
            active = now_active

        print(f"{w_idx:>4}  {rms:>8.5f}  {sf:>6.3f}  {'':>6}  "
              f"{scores.get('alarm_beep', 0):>10.4f}  "
              f"{scores.get('child_crying', 0):>12.4f}  "
              f"{str(sorted(fired_raw)):>30}  "
              f"{str(sorted(newly)) if newly else '':>30}")

    print("─" * 120)
    print(f"\nSummary: {w_idx} windows total")
    print(f"  Gated (silent):      {gated}")
    print(f"  Below threshold:     {below_thresh}")
    print(f"  Above threshold:     {fired_windows}")
    print(f"  Smoother emissions:  {len(active)} labels currently active at end")


if __name__ == "__main__":
    paths = sys.argv[1:] or [
        "test_audio/smoke-alarm.mp3",
        "test_audio/baby-crying-high-pitch.mp3",
    ]
    for p in paths:
        run(p)
