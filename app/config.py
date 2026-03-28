"""Application configuration loaded from environment variables / .env file."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All runtime configuration for SoundSense backend."""

    OPENAI_API_KEY: str = ""
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    CLASSIFIER_MODE: str = "fake"  # "fake" or "panns"
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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
