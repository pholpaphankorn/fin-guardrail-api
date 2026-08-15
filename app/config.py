"""Validated runtime configuration sourced from environment variables."""

import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr

load_dotenv()


class Settings(BaseModel):
    use_mock_llm: bool = False
    ollama_api_key: SecretStr | None = None
    ollama_host: str = "https://ollama.com"
    vision_model: str = "gemma4:31b-cloud"
    vision_timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)

    @property
    def live_provider_ready(self) -> bool:
        return self.use_mock_llm or self.ollama_api_key is not None


def get_settings() -> Settings:
    """Read settings at call time so deployment overrides remain predictable."""
    return Settings.model_validate(
        {
            "use_mock_llm": os.environ.get("USE_MOCK_LLM", "false"),
            "ollama_api_key": os.environ.get("OLLAMA_API_KEY") or None,
            "ollama_host": os.environ.get("OLLAMA_HOST", "https://ollama.com"),
            "vision_model": os.environ.get("VISION_MODEL", "gemma4:31b-cloud"),
            "vision_timeout_seconds": os.environ.get("VISION_TIMEOUT_SECONDS", "30"),
        }
    )
