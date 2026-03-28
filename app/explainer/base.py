"""Abstract base class for all LLM explainer implementations."""

from abc import ABC, abstractmethod

from app.models.schemas import ExplainerContext, ExplainerResponse


class BaseExplainer(ABC):
    """Interface all explainer implementations must satisfy."""

    @abstractmethod
    def explain(self, context: ExplainerContext) -> ExplainerResponse:
        """Convert a situation context into a natural language explanation.

        Args:
            context: Structured context about the current situation flag.

        Returns:
            ExplainerResponse with a one-sentence explanation and urgency level.
        """
