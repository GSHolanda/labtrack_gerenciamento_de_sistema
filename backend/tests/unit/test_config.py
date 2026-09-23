import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_are_read_from_prefixed_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LABTRACK_ENVIRONMENT", "production")
    monkeypatch.setenv("LABTRACK_LOG_FORMAT", "json")
    monkeypatch.setenv("LABTRACK_CORS_ORIGINS", '["https://labtrack.example.com"]')

    settings = Settings(_env_file=None)

    assert settings.environment == "production"
    assert settings.log_format == "json"
    assert settings.cors_origins == ["https://labtrack.example.com"]


def test_invalid_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LABTRACK_ENVIRONMENT", "staging")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
