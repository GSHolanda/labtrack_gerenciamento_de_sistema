from collections.abc import Iterator

from sqlalchemy import select, text

from app.domain.pagination import PageRequest, PageResult
from app.models import AuditLog
from app.repositories.base import BaseRepository
from app.schemas.audit import AuditFilter

# Chave arbitrária do advisory lock que serializa a escrita na cadeia de hashes.
_AUDIT_CHAIN_LOCK_KEY = 7_415_001


class AuditRepository(BaseRepository[AuditLog]):
    """Somente inclusão e leitura: não existe método de alteração ou exclusão."""

    model = AuditLog
    sortable = {  # noqa: RUF012
        "occurred_at": AuditLog.occurred_at,
        "action": AuditLog.action,
        "id": AuditLog.id,
    }
    default_sort = (AuditLog.occurred_at.desc(),)

    def search(self, filters: AuditFilter, page: PageRequest) -> PageResult[AuditLog]:
        statement = select(AuditLog)
        for field in (
            "user_id",
            "instrument_id",
            "actor_type",
            "action",
            "entity_type",
            "entity_id",
            "sample_id",
        ):
            value = getattr(filters, field)
            if value is not None:
                statement = statement.where(getattr(AuditLog, field) == value)
        if filters.occurred_from is not None:
            statement = statement.where(AuditLog.occurred_at >= filters.occurred_from)
        if filters.occurred_to is not None:
            statement = statement.where(AuditLog.occurred_at <= filters.occurred_to)
        return self.paginate(statement, page)

    def chain(self) -> Iterator[AuditLog]:
        # Uma única consulta; no PostgreSQL o cursor mantém o snapshot de leitura.
        # yield_per limita memória sem carregar toda a trilha de uma vez.
        statement = select(AuditLog).order_by(AuditLog.id).execution_options(yield_per=500)
        with self.session.scalars(statement) as entries:
            yield from entries

    def lock_chain(self) -> None:
        """Garante que dois registros simultâneos não apontem para o mesmo anterior."""
        if self.session.get_bind().dialect.name == "postgresql":
            self.session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": _AUDIT_CHAIN_LOCK_KEY}
            )

    def last_hash(self) -> str | None:
        return self.session.scalar(
            select(AuditLog.record_hash).order_by(AuditLog.id.desc()).limit(1)
        )
