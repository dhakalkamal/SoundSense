"""CNN14 PANNs classifier — real audio inference for SoundSense."""

import csv
import logging
import random
import time
from pathlib import Path

import torch
import torchaudio
from panns_inference.models import Cnn14

from app.inference.base import BaseClassifier
from app.models.schemas import SoundEvent

logger = logging.getLogger(__name__)

SAMPLE_RATE = 32_000
CLIP_SAMPLES = SAMPLE_RATE * 10          # 10-second clip (REST / scenario engine)
WINDOW_SAMPLES = int(SAMPLE_RATE * 0.96)  # 0.96-second streaming window (~30720 samples)
CONFIDENCE_THRESHOLD = 0.3

# --- Legacy mapping kept for _infer_from_file() / REST endpoint ---
AUDIOSET_TO_SOUNDSENSE: dict[str, str] = {
    "Footsteps, footfall": "footsteps",
    "Walk, footsteps": "footsteps",
    "Door": "door_open",
    "Slam": "door_open",
    "Creak": "door_open",
    "Knock": "door_knock",
    "Bell": "doorbell",
    "Doorbell": "doorbell",
    "Alarm": "alarm_beep",
    "Beep, bleep": "alarm_beep",
    "Smoke detector, smoke alarm": "alarm_beep",
    "Carbon monoxide detector": "alarm_beep",
    "Water": "water_running",
    "Stream": "water_running",
    "Faucet": "water_running",
    "Sink (filling or washing)": "water_running",
    "Bathtub (filling or washing)": "water_running",
    "Bird": "birds",
    "Bird vocalization, bird call, bird song": "birds",
    "Chirp, tweet": "birds",
    "Shatter": "glass_break",
    "Glass": "glass_break",
    "Breaking": "glass_break",
    "Shouting": "raised_voices",
    "Screaming": "raised_voices",
    "Yell": "raised_voices",
    "Crying, sobbing": "child_crying",
    "Baby cry, infant cry": "child_crying",
    "Whimper": "child_crying",
}

# --- Streaming inference: 9 groups, keys are the SoundSense label names emitted ---
# Four groups map to existing reasoning-engine labels (alarm_beep, child_crying,
# glass_break, door_knock) so all 11 rules continue to fire unchanged.
# Five groups (phone_ringing, microwave, car_horn, dog_barking, doorbell) are
# new or preserved as-is; they appear in the event timeline but have no rules yet.
CLASS_GROUPS: dict[str, list[str]] = {
    "alarm_beep": [
        "Smoke detector, smoke alarm",   # idx 399
        "Fire alarm",                    # idx 400
        "Alarm",                         # idx 388
        "Beep, bleep",                   # idx 481
    ],
    "child_crying": [
        "Baby cry, infant cry",          # idx 23
        "Crying, sobbing",               # idx 22
        "Whimper",                       # idx 24 — "Whimper (dog)" is a distinct label (idx 80)
    ],
    "glass_break": [
        "Shatter",                       # idx 443
        "Glass",                         # idx 441
        "Breaking",                      # idx 470
    ],
    "phone_ringing": [
        "Telephone bell ringing",        # idx 390
        "Ringtone",                      # idx 391
        "Telephone",                     # idx 389
    ],
    "microwave": [
        "Microwave oven",                # idx 368
        # "Beep, bleep" lives in alarm_beep only; temporal disambiguation
        # in the WebSocket handler separates microwave bursts from sustained alarms.
    ],
    "car_horn": [
        "Vehicle horn, car horn, honking",  # idx 308
        "Honk",                             # idx 107
        "Air horn, truck horn",             # idx 318
    ],
    "dog_barking": [
        "Bark",                          # idx 75
        "Bow-wow",                       # idx 78
        "Dog",                           # idx 74
    ],
    "door_knock": [
        "Knock",                         # idx 359
        # "Tap" (idx 360) excluded — too generic (guitar technique, etc.)
    ],
    "doorbell": [
        "Doorbell",                      # idx 355
        "Ding-dong",                     # idx 356
    ],
}

# Per-class detection thresholds for streaming inference (sum of group scores).
# Start at 0.4 for all classes; tune after real-device testing.
PER_CLASS_THRESHOLDS: dict[str, float] = {
    "alarm_beep": 0.4,
    "child_crying": 0.4,
    "glass_break": 0.4,
    "phone_ringing": 0.4,
    "microwave": 0.4,
    "car_horn": 0.4,
    "dog_barking": 0.4,
    "door_knock": 0.4,
    "doorbell": 0.4,
}

_LABELS_CSV = Path(__file__).parent.parent.parent / "models" / "class_labels_indices.csv"


def _load_audioset_labels(csv_path: Path) -> list[str]:
    """Load AudioSet display names indexed by class index from CSV."""
    labels: list[str] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            labels.append(row["display_name"])
    return labels


def _make_model(device: str) -> Cnn14:
    """Instantiate Cnn14 with the training hyperparameters used for the checkpoint."""
    return Cnn14(
        sample_rate=SAMPLE_RATE,
        window_size=1024,
        hop_size=320,
        mel_bins=64,
        fmin=50,
        fmax=14000,
        classes_num=527,
    ).to(device)


class PANNsClassifier(BaseClassifier):
    """Real CNN14 audio inference classifier for SoundSense.

    Loads the PANNs checkpoint once on init and runs inference on mono 32 kHz
    waveforms. Falls back to fake behaviour when audio_path is not provided
    (keeping scenario engine compatibility).

    For real-time streaming, use infer_tensor() which accepts a pre-assembled
    0.96-second waveform tensor and returns per-class summed scores.
    """

    def __init__(self, checkpoint_path: str, device: str | None = None) -> None:
        """Load model, checkpoint, AudioSet labels, and precompute group indices.

        Args:
            checkpoint_path: Path to Cnn14_mAP=0.431.pth.
            device: 'cuda', 'mps', or 'cpu'. Auto-detected when None.
                    Note: panns_inference always runs on CPU regardless of device arg.
        """
        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        self._device = device

        # panns_inference's Cnn14 contains frozen spectrogram/logmel layers that are
        # not MPS-compatible. Load the model on CPU; inference is fast enough for our
        # window size and the library ignores the device arg for these layers.
        self._model = _make_model("cpu")
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        self._model.load_state_dict(checkpoint["model"])
        self._model.eval()

        self._labels = _load_audioset_labels(_LABELS_CSV)

        # Precompute AudioSet indices for each CLASS_GROUPS entry so infer_tensor()
        # does a direct index lookup instead of repeated string comparisons.
        _label_to_idx = {name: i for i, name in enumerate(self._labels)}
        self._group_indices: dict[str, list[int]] = {
            ss_label: [
                _label_to_idx[name]
                for name in audioset_names
                if name in _label_to_idx
            ]
            for ss_label, audioset_names in CLASS_GROUPS.items()
        }
        # Warn loudly if any AudioSet label string was not found in the CSV.
        for ss_label, audioset_names in CLASS_GROUPS.items():
            for name in audioset_names:
                if name not in _label_to_idx:
                    logger.warning(
                        "[SoundSense] CLASS_GROUPS: '%s' not found in AudioSet labels "
                        "(group: %s) — check spelling against class_labels_indices.csv",
                        name,
                        ss_label,
                    )

        logger.info(
            "[SoundSense] PANNsClassifier loaded (CPU) — checkpoint: %s",
            checkpoint_path,
        )

        # Warm-up: one dummy forward pass so the first real inference isn't slow.
        logger.info("[SoundSense] PANNs warm-up: running one dummy inference...")
        self.infer_tensor(torch.zeros(1, WINDOW_SAMPLES))
        logger.info("[SoundSense] PANNs warm-up complete.")

    def infer_tensor(self, waveform: torch.Tensor) -> dict[str, float]:
        """Run CNN14 on a raw waveform tensor; return per-group summed scores.

        Pads or trims the input to WINDOW_SAMPLES (0.96 s at 32 kHz) internally.
        All 9 SoundSense labels are present in the returned dict; values are in [0, 1].
        Compare each value against PER_CLASS_THRESHOLDS to decide whether a class fired.

        Args:
            waveform: Float32 tensor, shape (1, N) or (N,), 32 kHz mono.

        Returns:
            dict mapping SoundSense label → summed AudioSet score for that group.
        """
        if waveform.ndim == 2:
            waveform = waveform.squeeze(0)  # model expects (batch, data_length), not (1, 1, N)

        n = waveform.shape[0]
        if n < WINDOW_SAMPLES:
            waveform = torch.nn.functional.pad(waveform, (0, WINDOW_SAMPLES - n))
        else:
            waveform = waveform[:WINDOW_SAMPLES]

        # Model expects (batch_size, data_length); run on CPU (see __init__ note).
        waveform_batch = waveform.unsqueeze(0).cpu()  # (1, WINDOW_SAMPLES)
        with torch.no_grad():
            output = self._model(waveform_batch, None)
        scores = output["clipwise_output"].squeeze(0).tolist()

        return {
            label: sum(scores[i] for i in indices)
            for label, indices in self._group_indices.items()
        }

    def classify(
        self,
        hint: str | None = None,
        audio_path: str | None = None,
        confidence: float | None = None,
    ) -> SoundEvent:
        """Classify audio and return a SoundEvent.

        If audio_path is provided, runs real CNN14 inference.
        If only hint is provided, falls back to fake label emission
        (keeps scenario engine compatibility when running without audio).

        Args:
            hint: Sound label hint — used when audio_path is None.
            audio_path: Path to audio file for real inference.
            confidence: Override confidence (fake-mode only).

        Returns:
            SoundEvent with timestamp=time.time() and elapsed_s=0.0.
        """
        if audio_path is not None:
            return self._infer_from_file(audio_path)

        # Fake fallback — scenario engine compatibility
        label = hint or "unknown"
        conf = confidence if confidence is not None else random.uniform(0.72, 0.96)
        logger.debug("[SoundSense] PANNsClassifier fake fallback: %s (conf=%.3f)", label, conf)
        return SoundEvent(
            label=label,
            confidence=round(conf, 4),
            timestamp=time.time(),
            elapsed_s=0.0,
        )

    def _infer_from_file(self, audio_path: str) -> SoundEvent:
        """Load audio, run CNN14, map top AudioSet label to SoundSense label."""
        import librosa
        import numpy as np
        y, sr = librosa.load(audio_path, sr=None, mono=False)
        if y.ndim == 1:
            y = y[np.newaxis, :]  # (1, samples)
        waveform = torch.from_numpy(y.astype(np.float32))

        # Resample if needed
        if sr != SAMPLE_RATE:
            waveform = torchaudio.functional.resample(waveform, orig_freq=sr, new_freq=SAMPLE_RATE)

        # Mono: average channels
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        # Pad or trim to exactly 10 seconds
        n = waveform.shape[1]
        if n < CLIP_SAMPLES:
            waveform = torch.nn.functional.pad(waveform, (0, CLIP_SAMPLES - n))
        else:
            waveform = waveform[:, :CLIP_SAMPLES]

        # Model expects (batch_size, data_length)
        waveform_batch = waveform.cpu()  # already (1, CLIP_SAMPLES)
        with torch.no_grad():
            output = self._model(waveform_batch, None)
        scores = output["clipwise_output"].squeeze(0).tolist()

        # Collect classes above threshold, sorted by score descending
        above = sorted(
            ((i, score) for i, score in enumerate(scores) if score >= CONFIDENCE_THRESHOLD),
            key=lambda x: x[1],
            reverse=True,
        )

        for idx, score in above:
            if idx < len(self._labels):
                audioset_name = self._labels[idx]
                mapped = AUDIOSET_TO_SOUNDSENSE.get(audioset_name)
                if mapped:
                    logger.debug(
                        "[SoundSense] PANNs: %s → %s (conf=%.3f)", audioset_name, mapped, score
                    )
                    return SoundEvent(
                        label=mapped,
                        confidence=round(score, 4),
                        timestamp=time.time(),
                        elapsed_s=0.0,
                    )

        logger.debug("[SoundSense] PANNs: no mapping found above threshold.")
        return SoundEvent(label="unknown", confidence=0.0, timestamp=time.time(), elapsed_s=0.0)
