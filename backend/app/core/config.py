"""Configuração centralizada da aplicação.

Segue o princípio *12-factor*: toda configuração vem de variáveis de ambiente
(prefixo ``LABTRACK_``) ou de um arquivo ``.env``. Nenhum outro módulo lê
``os.environ`` diretamente.
"""

from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
DEV_JWT_SECRET = "dev-secret-change-me-in-production-please"
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

    jwt_secret_key: str = Field(default=DEV_JWT_SECRET, min_length=32)
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=5, le=24 * 60)

    # Nome impresso no cabeçalho dos relatórios.
    lab_name: str = Field(default="Laboratório de Controle de Qualidade", min_length=1)

    # Fuso do laboratório: agrupa indicadores por dia, semana e mês locais e é o
    # horário impresso nos relatórios. As datas continuam gravadas em UTC.
    lab_timezone: str = "America/Sao_Paulo"

    @field_validator("lab_timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Fuso horário desconhecido: {value}") from exc
        return value

    @model_validator(mode="after")
    def _production_needs_own_secret(self) -> "Settings":
        # Tokens assinados com uma chave pública no repositório seriam forjáveis.
        if self.environment == "production" and self.jwt_secret_key == DEV_JWT_SECRET:
            raise ValueError(
                "Em produção, defina LABTRACK_JWT_SECRET_KEY: a chave de desenvolvimento "
                "é recusada."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Retorna a configuração da aplicação (instância única, carregada sob demanda)."""
    return Settings()
