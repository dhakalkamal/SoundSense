"""Async scenario playback engine.

Drives the full pipeline: emit events → state → reasoning → explainer.
"""

import asyncio
import logging
import time

from app.explainer.base import BaseExplainer
from app.inference.base import BaseClassifier
from app.models.schemas import ExplainerContext, ExplainerResponse, SituationFlag, UrgencyLevel
from app.reasoning.engine import ReasoningEngine
from app.scenario.scenarios import SCENARIOS, ScenarioDefinition
from app.state.manager import StateManager

logger = logging.getLogger(__name__)

# Fallback urgency when explainer is unavailable
_FLAG_URGENCY: dict[SituationFlag, UrgencyLevel] = {
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


class ScenarioEngine:
    """Runs timed scenario event loops and drives the full reasoning pipeline."""

    def __init__(
        self,
        state_manager: StateManager,
        classifier: BaseClassifier,
        reasoning_engine: ReasoningEngine,
        explainer: BaseExplainer | None,
    ) -> None:
        """Inject all pipeline dependencies."""
        self._state_manager = state_manager
        self._classifier = classifier
        self._reasoning_engine = reasoning_engine
        self._explainer = explainer
        self._task: asyncio.Task | None = None
        self._current_scenario_name: str | None = None

    async def start(self, scenario_name: str) -> None:
        """Start a named scenario, stopping any currently running one first.

        Args:
            scenario_name: Key into SCENARIOS dict.

        Raises:
            KeyError: If scenario_name is not in SCENARIOS.
        """
        scenario = SCENARIOS[scenario_name]  # raises KeyError on unknown name

        # Stop existing scenario cleanly before starting a new one
        if self.is_running():
            self.stop()
            # Allow the cancelled task to settle
            await asyncio.sleep(0)

        self._state_manager.reset()
        self._current_scenario_name = scenario_name
        self._task = asyncio.create_task(self._run_loop(scenario))
        logger.info("Scenario started: %s", scenario_name)

    def stop(self) -> None:
        """Cancel the running scenario task and reset all state."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None
        self._current_scenario_name = None
        self._state_manager.reset()
        logger.info("Scenario stopped and state cleared.")

    def is_running(self) -> bool:
        """Return True if a scenario task is currently active."""
        return self._task is not None and not self._task.done()

    def current_scenario_name(self) -> str | None:
        """Return the name of the currently running scenario, or None."""
        return self._current_scenario_name if self.is_running() else None

    async def _run_loop(self, scenario: ScenarioDefinition) -> None:
        """Run all scenario events in timed sequence, driving the full pipeline."""
        start_time = time.time()
        self._state_manager.set_scenario(scenario.name, start_time)

        current_flag = SituationFlag.NONE

        sorted_events = sorted(scenario.events, key=lambda e: e.delay_s)

        try:
            for scene_event in sorted_events:
                # Sleep until this event's scheduled time
                target = start_time + scene_event.delay_s
                wait = target - time.time()
                if wait > 0:
                    await asyncio.sleep(wait)

                now = time.time()

                # Classify (FakeClassifier uses fixed confidence from scenario)
                sound_event = self._classifier.classify(
                    hint=scene_event.label,
                    confidence=scene_event.confidence,
                )
                sound_event.elapsed_s = now - start_time

                # Update state
                self._state_manager.add_event(sound_event)
                self._state_manager.decay_inactive(now)

                # Evaluate reasoning
                snapshot = self._state_manager.get_snapshot()
                new_flag = self._reasoning_engine.evaluate(snapshot, now)

                logger.debug(
                    "t=%.1fs  label=%s  flag=%s",
                    sound_event.elapsed_s,
                    scene_event.label,
                    new_flag.value,
                )

                # Only call explainer on flag transitions
                if new_flag != current_flag:
                    current_flag = new_flag
                    explanation, urgency = self._call_explainer(snapshot, new_flag, now)
                    elapsed_s = now - start_time
                    self._state_manager.set_situation(new_flag, explanation, urgency, now)
                    self._state_manager.add_alert(new_flag, explanation, urgency, elapsed_s)
                    logger.info(
                        "Flag changed → %s (%s): %s", new_flag.value, urgency.value, explanation
                    )

        except asyncio.CancelledError:
            logger.info("Scenario '%s' cancelled.", scenario.name)
            raise
        finally:
            # Mark scenario as no longer running (keep event state for polling)
            self._state_manager.set_scenario(None, None)
            self._current_scenario_name = None

    def _call_explainer(
        self,
        snapshot,
        flag: SituationFlag,
        now: float,
    ) -> tuple[str, UrgencyLevel]:
        """Call the explainer if available, otherwise return a safe fallback."""
        if self._explainer is None:
            return "Sound activity noted nearby.", _FLAG_URGENCY.get(flag, UrgencyLevel.low)

        try:
            context: ExplainerContext = self._reasoning_engine.get_explainer_context(
                snapshot, flag, now
            )
            response: ExplainerResponse = self._explainer.explain(context)
            return response.explanation, response.urgency
        except Exception as exc:  # noqa: BLE001
            logger.warning("Explainer error for %s: %s — using fallback.", flag.value, exc)
            return "Sound activity noted nearby.", _FLAG_URGENCY.get(flag, UrgencyLevel.low)
