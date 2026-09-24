"""Exceções da aplicação.

Serviços e domínio sinalizam falhas com estas classes, sem conhecer HTTP. A
camada ``api`` converte cada tipo no status HTTP adequado e no envelope de
erro padrão. O ``code`` é estável e pode ser tratado pelos clientes.
"""

from typing import Any


class AppError(Exception):
    code = "APP_ERROR"

    def __init__(
        self, message: str, *, code: str | None = None, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.code
        self.details = details


class NotFoundError(AppError):
    code = "NOT_FOUND"


class ConflictError(AppError):
    """Conflito com o estado atual (ex.: transição de status inválida)."""

    code = "CONFLICT"


class BusinessRuleError(AppError):
    """Valor informado viola uma regra de negócio (ex.: unidade incompatível)."""

    code = "BUSINESS_RULE_VIOLATION"


class AuthenticationError(AppError):
    code = "NOT_AUTHENTICATED"


class PermissionDeniedError(AppError):
    code = "PERMISSION_DENIED"
