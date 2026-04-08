"""Application configuration loaded from environment variables / .env file."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All runtime configuration for SoundSense backend."""

    OPENAI_API_KEY: str = ""
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    CLASSIFIER_MODE: str = "fake"  # "fake" | "panns" | "yamnet"
    YAMNET_MODEL_URL: str = "https://tfhub.dev/google/yamnet/1"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8081",
        "http://localhost:19006",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8081",
    ]

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-haiku-4-5-20251001"
    PANNS_CHECKPOINT: str = "models/Cnn14_mAP=0.431.pth"

    # WebSocket streaming pipeline settings
    WS_HOP_SAMPLES: int = 15360          # 50% overlap at 32 kHz (~0.48 s)
    WS_ENERGY_RMS_THRESHOLD: float = 0.001   # below this RMS → check flatness
    WS_ENERGY_SF_THRESHOLD: float = 0.85     # spectral flatness above this → silent
    WS_SMOOTH_WINDOW: int = 3            # number of consecutive windows to vote over
    WS_SMOOTH_MIN_HITS: int = 2          # minimum hits in window to emit a detection

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
