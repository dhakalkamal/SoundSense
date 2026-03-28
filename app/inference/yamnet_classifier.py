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
    "Knock": "door_knock",
    "Tap": "door_knock",
    "Door": "door_open",
    "Creak": "door_open",
    "Slam": "door_open",
    "Doorbell": "doorbell",
    "Bell": "doorbell",
    "Chime": "doorbell",
    "Alarm": "alarm_beep",
    "Beep, bleep": "alarm_beep",
    "Smoke detector, smoke alarm": "alarm_beep",
    "Carbon monoxide detector": "alarm_beep",
    "Buzzer": "alarm_beep",
    "Walk, footsteps": "footsteps",
    "Footsteps": "footsteps",
    "Water": "water_running",
    "Sink (filling or washing)": "water_running",
    "Faucet": "water_running",
    "Stream": "water_running",
    "Bathtub (filling or washing)": "water_running",
    "Bird": "birds",
    "Bird vocalization, bird call, bird song": "birds",
    "Chirp, tweet": "birds",
    "Shatter": "glass_break",
    "Glass": "glass_break",
    "Breaking": "glass_break",
    "Screaming": "raised_voices",
    "Shouting": "raised_voices",
    "Yell": "raised_voices",
    "Baby cry, infant cry": "child_crying",
    "Crying, sobbing": "child_crying",
    "Whimper": "child_crying",
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

        Args:
            audio_path: Path to the audio file.

        Returns:
            SoundEvent with the best-mapped SoundSense label and its score.
        """
        import librosa

        tf = self._tf

        y, _ = librosa.load(audio_path, sr=YAMNET_SAMPLE_RATE, mono=True)
        waveform = tf.constant(y, dtype=tf.float32)

        scores, _embeddings, _spectrogram = self._model(waveform)
        mean_scores = tf.reduce_mean(scores, axis=0).numpy()

        # Sort class indices by score descending, keep those above 0.1
        sorted_indices = mean_scores.argsort()[::-1]
        for idx in sorted_indices:
            score = float(mean_scores[idx])
            if score < 0.1:
                break
            class_name = self._class_names[idx]
            mapped = YAMNET_TO_SOUNDSENSE.get(class_name)
            if mapped:
                logger.debug("YAMNet: %s → %s (score=%.3f)", class_name, mapped, score)
                return SoundEvent(
                    label=mapped,
                    confidence=score,
                    timestamp=time.time(),
                    elapsed_s=0.0,
                )

        logger.debug("YAMNet: no mapping found above threshold")
        return SoundEvent(label="unknown", confidence=0.0, timestamp=time.time(), elapsed_s=0.0)
