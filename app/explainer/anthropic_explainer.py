"""Anthropic Claude-backed LLM explainer for SoundSense."""

import json
import logging

import anthropic

from app.explainer.base import BaseExplainer
from app.explainer.openai_explainer import (
    FLAG_DEFAULT_URGENCY,
    _SYSTEM_PROMPT,
    _URGENCY_RANK,
    _build_user_message,
    _fallback,
)
from app.models.schemas import ExplainerContext, ExplainerResponse, UrgencyLevel

logger = logging.getLogger(__name__)


class AnthropicExplainer(BaseExplainer):
    """Calls Anthropic Claude to generate situation explanations for SoundSense."""

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001") -> None:
        """Initialise Anthropic client with API key and model name."""
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        logger.info("[SoundSense] AnthropicExplainer initialised (model=%s)", model)

    def explain(self, context: ExplainerContext) -> ExplainerResponse:
        """Call the Anthropic API and parse the JSON response.

        Enforces urgency floor from FLAG_DEFAULT_URGENCY.
        Falls back to a safe default on any exception.
        """
        try:
            message = self._client.messages.create(
                model=self._model,
                max_tokens=100,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _build_user_message(context)}],
            )
            raw = message.content[0].text if message.content else ""
            data = json.loads(raw)
            llm_urgency = UrgencyLevel(data["urgency"])
            floor = FLAG_DEFAULT_URGENCY.get(context.flag, UrgencyLevel.low)
            urgency = llm_urgency if _URGENCY_RANK[llm_urgency] >= _URGENCY_RANK[floor] else floor
            return ExplainerResponse(explanation=data["explanation"], urgency=urgency)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[SoundSense] AnthropicExplainer failed for %s: %s", context.flag.value, exc
            )
            return _fallback(context.flag)
