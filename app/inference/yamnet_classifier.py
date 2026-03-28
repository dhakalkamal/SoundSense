"""YAMNet-based audio classifier using TensorFlow Hub."""

import logging
import random
import time

from app.inference.base import BaseClassifier
from app.models.schemas import SoundEvent

logger = logging.getLogger(__name__)

YAMNET_MODEL_URL = "https://tfhub.dev/google/yamnet/1"
YAMNET_SAMPLE_RATE = 16000  # YAMNet requires 16kHz mono

YAMNET_TO_SOUNDSENSE = {
    # child_crying — highly distinctive, keep broad
    "Baby cry": "child_crying",
    "Crying": "child_crying",
    "Whimper": "child_crying",
    # alarm_beep — highly distinctive electronic sounds
    "Fire alarm": "alarm_beep",
    "Smoke detector": "alarm_beep",
    "Alarm": "alarm_beep",
    "Siren": "alarm_beep",
    "Civil defense siren": "alarm_beep",
    "Beep": "alarm_beep",
    "Buzzer": "alarm_beep",
    # glass_break — very distinctive transient
    "Shatter": "glass_break",
    "Breaking": "glass_break",
    # raised_voices
    "Screaming": "raised_voices",
    "Shouting": "raised_voices",
    "Children shouting": "raised_voices",
    # water_running — ONLY the most specific classes; broad ones (Waterfall,
    # Gurgling, Rain) cause false positives when mic captures YouTube audio
    "Sink (filling or washing)": "water_running",
    "Faucet": "water_running",
    "Bathtub (filling or washing)": "water_running",
    "Water": "water_running",
    # footsteps
    "Walk, footsteps": "footsteps",
    # door_knock
    "Knock": "door_knock",
    # doorbell
    "Doorbell": "doorbell",
}

# Per-class minimum confidence thresholds.
# Water gets a high bar (false-positive prone via mic).
# Baby cry and fire alarm get a lower bar (distinctive sounds, don't miss them).
LABEL_THRESHOLDS: dict[str, float] = {
    "child_crying": 0.20,
    "alarm_beep": 0.20,
    "glass_break": 0.25,
    "raised_voices": 0.25,
    "water_running": 0.50,   # must be unambiguously water
    "footsteps": 0.35,
    "door_knock": 0.35,
    "doorbell": 0.30,
}


class YAMNetClassifier(BaseClassifier):
    """Audio classifier using Google YAMNet via TensorFlow Hub.

    Accepts raw audio files (any format supported by librosa) or hint labels
    for scenario-engine fallback mode.
    """

    def __init__(self):
        """Load YAMNet model and AudioSet class names from TensorFlow Hub."""
        import tensorflow as tf
        import tensorflow_hub as hub

        self._tf = tf
        self._model = hub.load(YAMNET_MODEL_URL)

        class_map_path = self._model.class_map_path().numpy().decode()
        self._class_names = [
            line.strip().split(",")[2].strip('"')
            for line in tf.io.gfile.GFile(class_map_path).readlines()[1:]
        ]
        logger.info("YAMNetClassifier loaded — %d AudioSet classes", len(self._class_names))

    def classify(
        self,
        hint: str | None = None,
        audio_path: str | None = None,
        confidence: float | None = None,
    ) -> SoundEvent:
        """Classify audio from a file path or fall back to hint label.

        Args:
            hint: Label hint for fake/scenario fallback when no audio_path given.
            audio_path: Path to audio file to classify with YAMNet.
            confidence: Confidence override used only in hint-fallback mode.

        Returns:
            SoundEvent with the classified label, confidence, and current timestamp.
        """
        if audio_path is not None:
            try:
                return self._classify_audio(audio_path)
            except Exception as exc:
                logger.error("YAMNetClassifier error on %s: %s", audio_path, exc)
                return SoundEvent(label="unknown", confidence=0.0, timestamp=time.time(), elapsed_s=0.0)

        # Hint fallback — mirrors FakeClassifier behaviour for scenario engine
        if hint is not None:
            if confidence is None:
                confidence = random.uniform(0.72, 0.96)
            logger.debug("YAMNetClassifier (hint fallback): %s (conf=%.3f)", hint, confidence)
            return SoundEvent(
                label=hint,
                confidence=round(confidence, 4),
                timestamp=time.time(),
                elapsed_s=0.0,
            )

        logger.warning("YAMNetClassifier called with no audio_path and no hint")
        return SoundEvent(label="unknown", confidence=0.0, timestamp=time.time(), elapsed_s=0.0)

    def _classify_audio(self, audio_path: str) -> SoundEvent:
        """Run YAMNet inference on an audio file and return a mapped SoundEvent.

        Uses ffmpeg to normalise any input format (M4A, WebM, OGG, CAF, etc.)
        into a clean 16 kHz mono WAV before passing to librosa. This decouples
        format detection from classification and avoids librosa's format limits.

        Args:
            audio_path: Path to the audio file in any ffmpeg-supported format.

        Returns:
            SoundEvent with the best-mapped SoundSense label and its score.
        """
        import subprocess
        import numpy as np

        tf = self._tf

        # Convert to 16kHz mono WAV using ffmpeg regardless of input format
        wav_path = audio_path + "_converted.wav"
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", audio_path,
                    "-ar", str(YAMNET_SAMPLE_RATE),
                    "-ac", "1",
                    "-f", "wav",
                    wav_path,
                ],
                capture_output=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.warning("[YAMNet] ffmpeg failed: %s", result.stderr.decode()[-300:])
                raise RuntimeError("ffmpeg conversion failed")

            import librosa
            y, _ = librosa.load(wav_path, sr=YAMNET_SAMPLE_RATE, mono=True)
        finally:
            import os as _os
            if _os.path.exists(wav_path):
                _os.unlink(wav_path)

        rms = float(np.sqrt(np.mean(y ** 2)))
        duration = len(y) / YAMNET_SAMPLE_RATE
        logger.info("[YAMNet] audio: duration=%.2fs rms=%.4f samples=%d", duration, rms, len(y))
        if rms < 0.001:
            logger.warning("[YAMNet] audio is nearly silent — chunk likely noise")

        waveform = tf.constant(y, dtype=tf.float32)

        scores, _embeddings, _spectrogram = self._model(waveform)
        mean_scores = tf.reduce_mean(scores, axis=0).numpy()

        # Sort class indices by score descending, keep those above 0.1
        sorted_indices = mean_scores.argsort()[::-1]

        # Log top-5 raw classes so we can see what YAMNet actually hears
        top5 = [(self._class_names[i], float(mean_scores[i])) for i in sorted_indices[:5]]
        logger.info("[YAMNet] top-5: %s", [(n, f"{s:.3f}") for n, s in top5])

        # Walk classes in score order; apply per-label threshold
        for idx in sorted_indices:
            score = float(mean_scores[idx])
            if score < 0.10:  # absolute floor — nothing below this is meaningful
                break
            class_name = self._class_names[idx]
            label = YAMNET_TO_SOUNDSENSE.get(class_name)
            if label is None:
                continue
            threshold = LABEL_THRESHOLDS.get(label, 0.25)
            if score >= threshold:
                logger.info("[YAMNet] %s → %s (score=%.3f, threshold=%.2f)", class_name, label, score, threshold)
                return SoundEvent(
                    label=label,
                    confidence=score,
                    timestamp=time.time(),
                    elapsed_s=0.0,
                )

        logger.info("[YAMNet] no label met threshold — top was: %s (%.3f)", top5[0][0] if top5 else "?", top5[0][1] if top5 else 0)
        return SoundEvent(label="unknown", confidence=0.0, timestamp=time.time(), elapsed_s=0.0)
