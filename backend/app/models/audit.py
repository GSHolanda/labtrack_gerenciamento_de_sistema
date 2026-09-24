from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, IdMixin, JsonDocument, enum_check
from app.domain.enums import ActorType


class AuditLog(IdMixin, Base):
    """Registro do audit trail. Append-only: nunca é alterado nem excluído.

    A imutabilidade é garantida também no banco (trigger criado na migração) e
    por hash encadeado (``previous_hash`` → ``record_hash``).
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        enum_check("actor_type", ActorType),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )

    occurred_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    actor_type: Mapped[str] = mapped_column(String(12))
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    instrument_id: Mapped[int | None] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT")
    )
    actor_name: Mapped[str] = mapped_column(String(150))
    action: Mapped[str] = mapped_column(String(50), index=True)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(50))
    entity_label: Mapped[str | None] = mapped_column(String(120))
    sample_id: Mapped[int | None] = mapped_column(
        ForeignKey("samples.id", ondelete="RESTRICT"), index=True
    )
    old_value: Mapped[Any | None] = mapped_column(JsonDocument)
    new_value: Mapped[Any | None] = mapped_column(JsonDocument)
    reason: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(64))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    previous_hash: Mapped[str | None] = mapped_column(CHAR(64))
    record_hash: Mapped[str] = mapped_column(CHAR(64), unique=True)
