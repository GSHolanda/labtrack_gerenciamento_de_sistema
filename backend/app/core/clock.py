"""Relógio da aplicação.

Os serviços registram o momento dos eventos de negócio (auditoria, transições,
resultados) por aqui, e não com ``datetime.now`` espalhado pelo código. Na API
é sempre o relógio real. Só a geração de dados de demonstração fixa o relógio,
para distribuir o histórico nas semanas anteriores de forma cronológica.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, date, datetime

_frozen_at: ContextVar[datetime | None] = ContextVar("labtrack_frozen_at", default=None)


def utcnow() -> datetime:
    return _frozen_at.get() or datetime.now(UTC)


def utctoday() -> date:
    return utcnow().date()


@contextmanager
def frozen_at(moment: datetime) -> Iterator[None]:
    """Fixa o relógio em ``moment`` (com fuso) dentro do bloco."""
    if moment.tzinfo is None:
        raise ValueError("O momento precisa ter fuso horário.")
    token = _frozen_at.set(moment.astimezone(UTC))
    try:
        yield
    finally:
        _frozen_at.reset(token)
