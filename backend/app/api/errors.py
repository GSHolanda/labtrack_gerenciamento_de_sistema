"""Tradução de exceções para respostas HTTP no envelope de erro padrão."""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import (
    AppError,
    AuthenticationError,
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from app.core.request_context import get_request_id

logger = logging.getLogger(__name__)

STATUS_BY_ERROR: dict[type[AppError], int] = {
    NotFoundError: 404,
    ConflictError: 409,
    BusinessRuleError: 422,
    AuthenticationError: 401,
    PermissionDeniedError: 403,
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": get_request_id(),
        }
    }
    return JSONResponse(jsonable_encoder(body), status_code=status_code, headers=headers)


def _status_for(exc: AppError) -> int:
    for error_type in type(exc).__mro__:
        if error_type in STATUS_BY_ERROR:
            return STATUS_BY_ERROR[error_type]
    return 400


async def _app_error(_: Request, exc: AppError) -> JSONResponse:
    status_code = _status_for(exc)
    headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
    return error_response(status_code, exc.code, exc.message, exc.details, headers)


async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"field": ".".join(str(part) for part in err["loc"]), "message": err["msg"]}
        for err in exc.errors()
    ]
    return error_response(422, "VALIDATION_ERROR", "Dados inválidos na requisição.", details)


async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    phrase = HTTPStatus(exc.status_code).phrase
    code = phrase.upper().replace(" ", "_")
    message = exc.detail if isinstance(exc.detail, str) else phrase
    return error_response(exc.status_code, code, message, headers=exc.headers)


async def _stale_data(_: Request, exc: StaleDataError) -> JSONResponse:
    logger.info("Conflito de concorrência: %s", exc)
    return error_response(
        409,
        "CONCURRENT_MODIFICATION",
        "O registro foi alterado por outro usuário. Recarregue e tente novamente.",
    )


async def _integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
    # O detalhe do banco pode expor estrutura interna: vai para o log, não para o cliente.
    logger.warning("Violação de integridade: %s", exc.orig)
    return error_response(
        409, "DATA_INTEGRITY_VIOLATION", "A operação viola uma regra de integridade dos dados."
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_error)  # type: ignore[arg-type]
    app.add_exception_handler(StaleDataError, _stale_data)  # type: ignore[arg-type]
    app.add_exception_handler(IntegrityError, _integrity_error)  # type: ignore[arg-type]
