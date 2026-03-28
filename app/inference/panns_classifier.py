"""CNN14 PANNs classifier — real audio inference for SoundSense."""

import csv
import logging
import random
import time
from pathlib import Path

import torch
import torchaudio
import torchaudio.transforms as T

from app.inference.base import BaseClassifier
from app.inference.panns_model import Cnn14
from app.models.schemas import SoundEvent

logger = logging.getLogger(__name__)

SAMPLE_RATE = 32_000
CLIP_SAMPLES = SAMPLE_RATE * 10  # 10-second clip
CONFIDENCE_THRESHOLD = 0.3

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

_LABELS_CSV = Path(__file__).parent.parent.parent / "models" / "class_labels_indices.csv"


def _load_audioset_labels(csv_path: Path) -> list[str]:
    """Load AudioSet display names indexed by class index from CSV."""
    labels: list[str] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            labels.append(row["display_name"])
    return labels


class PANNsClassifier(BaseClassifier):
    """Real CNN14 audio inference classifier for SoundSense.

    Loads the PANNs checkpoint once on init and runs mel-spectrogram inference
    on 10-second mono 32kHz audio clips. Falls back to fake behaviour when
    audio_path is not provided (keeping scenario engine compatibility).
    """

    def __init__(self, checkpoint_path: str, device: str | None = None) -> None:
        """Load model, checkpoint, mel transform, and AudioSet label list.

        Args:
            checkpoint_path: Path to Cnn14_mAP=0.431.pth.
            device: 'cuda', 'mps', or 'cpu'. Auto-detected when None.
        """
        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        self._device = device

        self._model = Cnn14()
        checkpoint = torch.load(checkpoint_path, map_location=device)
        self._model.load_state_dict(checkpoint["model"], strict=False)
        self._model.to(device)
        self._model.eval()

        self._mel = T.MelSpectrogram(
            sample_rate=SAMPLE_RATE,
            n_fft=1024,
            hop_length=320,
            n_mels=64,
            f_min=50.0,
            f_max=14000.0,
        ).to(device)

        self._labels = _load_audioset_labels(_LABELS_CSV)

        logger.info(
            "[SoundSense] PANNsClassifier loaded on %s — checkpoint: %s",
            device,
            checkpoint_path,
        )

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
        """Load audio, compute mel spectrogram, run CNN14, map to SoundSense label."""
        waveform, sr = torchaudio.load(audio_path)

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

        waveform = waveform.to(self._device)

        # Mel spectrogram: torchaudio returns (channel, n_mels, time)
        mel = self._mel(waveform)  # (1, n_mels, time)
        # Reshape to (batch, time, mel_bins) as expected by Cnn14.forward
        mel = mel.squeeze(0).transpose(0, 1).unsqueeze(0)  # (1, time, mel_bins)

        with torch.no_grad():
            logits = self._model(mel)  # (1, 527)

        scores = logits.squeeze(0).cpu()

        # Collect classes above threshold, sorted by score descending
        above = sorted(
            ((i, float(scores[i])) for i in range(len(scores)) if scores[i] >= CONFIDENCE_THRESHOLD),
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
