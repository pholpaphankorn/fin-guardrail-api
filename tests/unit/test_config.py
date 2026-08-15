import pytest
from pydantic import ValidationError

from app.config import get_settings


@pytest.mark.unit
def test_settings_parse_mock_mode(monkeypatch):
    monkeypatch.setenv("USE_MOCK_LLM", "true")
    monkeypatch.setenv("VISION_TIMEOUT_SECONDS", "12.5")

    settings = get_settings()

    assert settings.use_mock_llm is True
    assert settings.vision_timeout_seconds == 12.5
    assert settings.live_provider_ready is True


@pytest.mark.unit
def test_settings_reject_invalid_timeout(monkeypatch):
    monkeypatch.setenv("VISION_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValidationError):
        get_settings()
