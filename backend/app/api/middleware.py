"""Middleware de contexto: request id, log de acesso e proteção contra erros inesperados."""

import logging
import re
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.errors import error_response
from app.core.request_context import reset_request_id, set_request_id

logger = logging.getLogger("labtrack.access")

REQUEST_ID_HEADER = "x-request-id"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestContextMiddleware:
    """ASGI puro (sem BaseHTTPMiddleware) para não interferir em streaming e contextvars.

    - Reaproveita o ``X-Request-ID`` recebido (se válido) ou gera um novo;
    - devolve o id no header da resposta e no corpo de erros;
    - registra método, rota, status e duração de cada requisição;
    - converte exceções não tratadas em 500 com envelope padrão, sem vazar detalhes.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(REQUEST_ID_HEADER.encode(), b"").decode()
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = set_request_id(request_id)
        started = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.encode(), request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            logger.exception("Erro não tratado")
            if response_started:
                raise
            response = error_response(500, "INTERNAL_ERROR", "Erro interno inesperado.")
            await response(scope, receive, send_with_request_id)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "%s %s -> %s (%.1f ms)", scope["method"], scope["path"], status_code, elapsed_ms
            )
            reset_request_id(token)
