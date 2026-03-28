"""Fake classifier that returns hardcoded labels for scenario playback."""

import logging
import random
import time

from app.inference.base import BaseClassifier
from app.models.schemas import SoundEvent

logger = logging.getLogger(__name__)


class FakeClassifier(BaseClassifier):
    """Returns SoundEvent with the given hint label and a realistic fake confidence."""

    def classify(self, hint: str, confidence: float | None = None) -> SoundEvent:
        """Build a SoundEvent from a label hint without real audio inference.

        Args:
            hint: Sound class label to emit.
            confidence: If None, a random value in [0.72, 0.96] is used.

        Returns:
            SoundEvent with current timestamp and elapsed_s=0.0.
            The scenario engine updates elapsed_s after classify() returns.
        """
        if confidence is None:
            confidence = random.uniform(0.72, 0.96)

        event = SoundEvent(
            label=hint,
            confidence=round(confidence, 4),
            timestamp=time.time(),
            elapsed_s=0.0,
        )
        logger.debug("FakeClassifier: %s (conf=%.3f)", hint, confidence)
        return event
