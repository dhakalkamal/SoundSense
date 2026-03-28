"""Abstract base class for all sound classifiers."""

from abc import ABC, abstractmethod

from app.models.schemas import SoundEvent


class BaseClassifier(ABC):
    """Interface all classifier implementations must satisfy."""

    @abstractmethod
    def classify(self, hint: str, confidence: float | None = None) -> SoundEvent:
        """Classify a sound and return a SoundEvent.

        Args:
            hint: The target sound class label string.
            confidence: Fixed confidence score. If None, the implementation
                        generates a realistic value.

        Returns:
            SoundEvent with timestamp set to time.time() and elapsed_s=0.0.
        """
