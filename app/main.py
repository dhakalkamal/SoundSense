"""FastAPI application entry point for SoundSense."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.explainer.anthropic_explainer import AnthropicExplainer
from app.explainer.base import BaseExplainer
from app.explainer.gemini_explainer import GeminiExplainer
from app.explainer.openai_explainer import OpenAIExplainer
from app.inference.base import BaseClassifier
from app.inference.fake_classifier import FakeClassifier
from app.inference.panns_classifier import PANNsClassifier
from app.reasoning.engine import ReasoningEngine
from app.scenario.engine import ScenarioEngine
from app.state.manager import StateManager

logging.basicConfig(level=settings.LOG_LEVEL.upper())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise all SoundSense pipeline components on startup."""

    # ── Classifier ────────────────────────────────────────────────────────────
    classifier: BaseClassifier
    if settings.CLASSIFIER_MODE == "yamnet":
        logger.info("[SoundSense] Starting with YAMNet classifier")
        from app.inference.yamnet_classifier import YAMNetClassifier
        classifier = YAMNetClassifier()
    elif settings.CLASSIFIER_MODE == "panns":
        logger.info("[SoundSense] Starting with PANNs CNN14 classifier")
        classifier = PANNsClassifier(settings.PANNS_CHECKPOINT)
    else:
        logger.info("[SoundSense] Starting with fake classifier")
        classifier = FakeClassifier()

    # ── Explainer ─────────────────────────────────────────────────────────────
    explainer: BaseExplainer | None = None
    if settings.LLM_PROVIDER == "gemini" and settings.GEMINI_API_KEY:
        explainer = GeminiExplainer(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
        )
    elif settings.LLM_PROVIDER == "anthropic" and settings.ANTHROPIC_API_KEY:
        explainer = AnthropicExplainer(
            api_key=settings.ANTHROPIC_API_KEY,
            model=settings.ANTHROPIC_MODEL,
        )
    elif settings.OPENAI_API_KEY:
        explainer = OpenAIExplainer(
            api_key=settings.OPENAI_API_KEY,
            model=settings.LLM_MODEL,
        )
    else:
        logger.warning("[SoundSense] No LLM API key found — explainer disabled")

    # ── Core pipeline ─────────────────────────────────────────────────────────
    state_manager = StateManager()
    reasoning_engine = ReasoningEngine()
    scenario_engine = ScenarioEngine(
        state_manager=state_manager,
        classifier=classifier,
        reasoning_engine=reasoning_engine,
        explainer=explainer,
    )

    # Attach to app.state so routes can access them
    app.state.settings = settings
    app.state.state_manager = state_manager
    app.state.classifier = classifier
    app.state.reasoning_engine = reasoning_engine
    app.state.explainer = explainer
    app.state.scenario_engine = scenario_engine
    app.state.emergency_contact = None  # set via POST /user/emergency-contact
    app.state.missed_alerts: list[dict] = []  # log of unread high/critical alerts

    yield

    # Graceful shutdown
    if scenario_engine.is_running():
        scenario_engine.stop()
    logger.info("[SoundSense] Backend shut down.")


app = FastAPI(title="SoundSense", version="0.1.0", lifespan=lifespan)

# Allow wildcard when CORS_ORIGINS=["*"] is set in .env, otherwise use explicit list
_cors_origins = settings.CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r".*" if _cors_origins == ["*"] else None,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    """Health check at root."""
    return {"status": "ok"}
