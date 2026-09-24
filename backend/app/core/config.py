"""Configuração centralizada da aplicação.

Segue o princípio *12-factor*: toda configuração vem de variáveis de ambiente
(prefixo ``LABTRACK_``) ou de um arquivo ``.env``. Nenhum outro módulo lê
``os.environ`` diretamente.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
LogFormat = Literal["text", "json"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LABTRACK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "LabTrack API"
    environment: Environment = "development"
    api_prefix: str = "/api/v1"

    log_level: LogLevel = "INFO"
    log_format: LogFormat = "text"

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    database_url: str = "postgresql+psycopg://labtrack:labtrack@localhost:5432/labtrack"
    database_echo: bool = False

    jwt_secret_key: str = Field(default="dev-secret-change-me-in-production-please", min_length=32)
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=5, le=24 * 60)


@lru_cache
def get_settings() -> Settings:
    """Retorna a configuração da aplicação (instância única, carregada sob demanda)."""
    return Settings()
