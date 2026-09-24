"""Configuração de logs da aplicação.

Dois formatos:
- ``text``: legível para desenvolvimento local;
- ``json``: uma linha JSON por evento, pronta para agregadores de log
  (ELK, Loki, CloudWatch etc.).
"""

import json
import logging
import sys
from datetime import UTC, datetime

from app.core.config import LogFormat, LogLevel
from app.core.request_context import RequestIdLogFilter

TEXT_FORMAT = "%(asctime)s | %(levelname)-8s | %(request_id)s | %(name)s | %(message)s"


class JsonFormatter(logging.Formatter):
    """Serializa cada registro de log como um objeto JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", "-")
        if request_id != "-":
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: LogLevel = "INFO", fmt: LogFormat = "text") -> None:
    """Configura o logger raiz e redireciona os loggers do Uvicorn para ele."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if fmt == "json" else logging.Formatter(TEXT_FORMAT))
    handler.addFilter(RequestIdLogFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # O log de acesso é feito pelo middleware da aplicação (com request id e duração).
    logging.getLogger("uvicorn.access").disabled = True
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
