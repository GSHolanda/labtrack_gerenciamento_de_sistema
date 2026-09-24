from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import AuditLog

# Chave arbitrária do advisory lock que serializa a escrita na cadeia de hashes.
_AUDIT_CHAIN_LOCK_KEY = 7_415_001


class AuditRepository:
    """Somente inclusão e leitura: não existe método de alteração ou exclusão."""

    def __init__(self, session: Session) -> None:
        self.session = session

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

    def add(self, entry: AuditLog) -> AuditLog:
        self.session.add(entry)
        self.session.flush()
        return entry
