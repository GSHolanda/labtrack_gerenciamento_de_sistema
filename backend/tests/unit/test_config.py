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


def test_lab_timezone_is_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    assert Settings(_env_file=None).lab_timezone == "America/Sao_Paulo"
    monkeypatch.setenv("LABTRACK_LAB_TIMEZONE", "Europe/Lisbon")
    assert Settings(_env_file=None).lab_timezone == "Europe/Lisbon"
    monkeypatch.setenv("LABTRACK_LAB_TIMEZONE", "Marte/Olympus")
    with pytest.raises(ValidationError, match="Fuso horário desconhecido"):
        Settings(_env_file=None)
