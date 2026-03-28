"""OpenAI-backed LLM explainer."""

import json
import logging

from openai import OpenAI

from app.explainer.base import BaseExplainer
from app.models.schemas import (
    ExplainerContext,
    ExplainerResponse,
    SituationFlag,
    UrgencyLevel,
)

logger = logging.getLogger(__name__)

# Default urgency per flag — used as fallback when LLM call fails or is skipped
_URGENCY_RANK: dict[UrgencyLevel, int] = {
    UrgencyLevel.low: 0,
    UrgencyLevel.medium: 1,
    UrgencyLevel.high: 2,
    UrgencyLevel.critical: 3,
}

FLAG_DEFAULT_URGENCY: dict[SituationFlag, UrgencyLevel] = {
    SituationFlag.SUDDEN_IMPACT: UrgencyLevel.critical,
    SituationFlag.CHILD_DISTRESS: UrgencyLevel.critical,
    SituationFlag.ALARM_ESCALATING: UrgencyLevel.high,
    SituationFlag.RAISED_VOICES_DETECTED: UrgencyLevel.high,
    SituationFlag.ARRIVAL_DETECTED: UrgencyLevel.medium,
    SituationFlag.KNOCK_OR_BELL: UrgencyLevel.medium,
    SituationFlag.WATER_RUNNING_LONG: UrgencyLevel.medium,
    SituationFlag.ALARM_SINGLE: UrgencyLevel.medium,
    SituationFlag.WATER_RUNNING_BRIEF: UrgencyLevel.low,
    SituationFlag.FOOTSTEPS_ONLY: UrgencyLevel.low,
    SituationFlag.CALM_AMBIENT: UrgencyLevel.low,
    SituationFlag.NONE: UrgencyLevel.low,
}

_SYSTEM_PROMPT = (
    "You are an assistive tool for deaf and hard-of-hearing users. "
    "Given a detected sound situation, write ONE clear calm sentence explaining what may be happening. "
    "Rules: use hedged language (may, appears to, seems like, you may want to). "
    "Never make definitive claims. Maximum 20 words. Do not start with I. "
    "Do not use the word detected. "
    'Respond ONLY with valid JSON: {"explanation": "...", "urgency": "low|medium|high|critical"}'
)


def _build_user_message(context: ExplainerContext) -> str:
    """Build the user message string from an ExplainerContext."""
    parts = [f"Situation flag: {context.flag.value}"]

    if context.recent_labels:
        parts.append(f"Recent sounds: {', '.join(context.recent_labels)}")

    if context.dominant_label:
        parts.append(f"Dominant sound: {context.dominant_label}")

    if context.duration_s is not None:
        parts.append(f"Duration: {int(context.duration_s)} seconds")

    if context.count is not None:
        parts.append(f"Repetition count: {context.count}")

    parts.append(f"Time of day: {context.time_of_day}")

    return "\n".join(parts)


def _fallback(flag: SituationFlag) -> ExplainerResponse:
    """Return a safe fallback explanation when the LLM call fails."""
    return ExplainerResponse(
        explanation="Sound activity noted nearby.",
        urgency=FLAG_DEFAULT_URGENCY.get(flag, UrgencyLevel.low),
    )


class OpenAIExplainer(BaseExplainer):
    """Calls OpenAI chat completions to generate situation explanations."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        """Initialise with an OpenAI API key and model name."""
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def explain(self, context: ExplainerContext) -> ExplainerResponse:
        """Call the OpenAI API and parse the JSON response.

        Falls back to a safe default if the call fails or returns invalid JSON.
        """
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _build_user_message(context)},
                ],
                max_tokens=100,
                temperature=0.4,
            )
            raw = response.choices[0].message.content or ""
            data = json.loads(raw)
            llm_urgency = UrgencyLevel(data["urgency"])
            floor = FLAG_DEFAULT_URGENCY.get(context.flag, UrgencyLevel.low)
            urgency = llm_urgency if _URGENCY_RANK[llm_urgency] >= _URGENCY_RANK[floor] else floor
            return ExplainerResponse(
                explanation=data["explanation"],
                urgency=urgency,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI explainer failed for %s: %s", context.flag.value, exc)
            return _fallback(context.flag)
