"""Gemini-backed LLM explainer for SoundSense."""

import json
import logging

from google import genai
from google.genai import types

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


class GeminiExplainer(BaseExplainer):
    """Calls Google Gemini to generate situation explanations for SoundSense."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash") -> None:
        """Configure Gemini client with API key and model name."""
        self._client = genai.Client(api_key=api_key)
        self._model_name = model
        self._config = types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.4,
            max_output_tokens=100,
        )
        logger.info("[SoundSense] GeminiExplainer initialised (model=%s)", model)

    def explain(self, context: ExplainerContext) -> ExplainerResponse:
        """Call the Gemini API and parse the JSON response.

        Enforces urgency floor from FLAG_DEFAULT_URGENCY.
        Falls back to a safe default on any exception.
        """
        try:
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=_build_user_message(context),
                config=self._config,
            )
            raw = response.text or ""
            data = json.loads(raw)
            llm_urgency = UrgencyLevel(data["urgency"])
            floor = FLAG_DEFAULT_URGENCY.get(context.flag, UrgencyLevel.low)
            urgency = llm_urgency if _URGENCY_RANK[llm_urgency] >= _URGENCY_RANK[floor] else floor
            return ExplainerResponse(explanation=data["explanation"], urgency=urgency)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[SoundSense] GeminiExplainer failed for %s: %s", context.flag.value, exc
            )
            return _fallback(context.flag)
