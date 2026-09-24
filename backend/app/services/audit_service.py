"""Gravação, consulta e verificação do audit trail.

É chamado pelos serviços **dentro da mesma transação** da operação auditada:
ou a alteração e seu registro são gravados juntos, ou nenhum dos dois.
"""

from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.request_context import get_request_id
from app.domain.audit import (
    HASHED_FIELDS,
    Actor,
    AuditAction,
    ChainEntry,
    ChainVerification,
    compute_record_hash,
    to_audit_value,
    verify_chain,
)
from app.domain.pagination import PageRequest, PageResult
from app.models import AuditLog
from app.repositories.audit_repository import AuditRepository
from app.repositories.sample_repository import SampleRepository
from app.schemas.audit import AuditFilter


class AuditService:
    def __init__(self, session: Session) -> None:
        self.repository = AuditRepository(session)
        self.samples = SampleRepository(session)

    def search(self, filters: AuditFilter, page: PageRequest) -> PageResult[AuditLog]:
        filters = replace(
            filters,
            occurred_from=_as_utc(filters.occurred_from),
            occurred_to=_as_utc(filters.occurred_to),
        )
        if (
            filters.occurred_from is not None
            and filters.occurred_to is not None
            and filters.occurred_from > filters.occurred_to
        ):
            raise BusinessRuleError(
                "O início do período deve ser anterior ou igual ao fim.",
                code="INVALID_DATE_RANGE",
            )
        return self.repository.search(filters, page)

    def verify(self) -> ChainVerification:
        with closing(self.repository.chain()) as records:
            entries = (
                ChainEntry(
                    entry.id, snapshot(entry, HASHED_FIELDS), entry.previous_hash, entry.record_hash
                )
                for entry in records
            )
            return verify_chain(entries)

    def timeline(self, sample_id: int, page: PageRequest) -> PageResult[AuditLog]:
        if self.samples.get(sample_id) is None:
            raise NotFoundError(f"Amostra {sample_id} não encontrada.", code="SAMPLE_NOT_FOUND")
        # Timeline sempre cronológica; desempate por ID feito pelo repositório base.
        return self.repository.search(
            AuditFilter(sample_id=sample_id), replace(page, sort="occurred_at")
        )

    def record(
        self,
        actor: Actor,
        action: AuditAction,
        *,
        entity_type: str,
        entity_id: int | str,
        entity_label: str | None = None,
        sample_id: int | None = None,
        old_value: Any = None,
        new_value: Any = None,
        reason: str | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        fields: dict[str, Any] = {
            "occurred_at": datetime.now(UTC),
            "actor_type": actor.type,
            "user_id": actor.user_id,
            "instrument_id": actor.instrument_id,
            "actor_name": actor.name,
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "entity_label": entity_label,
            "sample_id": sample_id,
            "old_value": to_audit_value(old_value),
            "new_value": to_audit_value(new_value),
            "reason": reason,
            "request_id": get_request_id(),
            "ip_address": ip_address,
        }
        self.repository.lock_chain()
        previous_hash = self.repository.last_hash()
        record_hash = compute_record_hash(fields, previous_hash)
        return self.repository.add(
            AuditLog(**fields, previous_hash=previous_hash, record_hash=record_hash)
        )


def actor_of(user: Any) -> Actor:
    return Actor.user(user.id, user.full_name)


def _as_utc(moment: datetime | None) -> datetime | None:
    if moment is None:
        return None
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def snapshot(entity: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    return {name: getattr(entity, name) for name in fields}


def diff(before: dict[str, Any], after: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Retorna apenas os campos alterados: (valores anteriores, novos valores)."""
    changed = [key for key in after if before.get(key) != after[key]]
    return {key: before.get(key) for key in changed}, {key: after[key] for key in changed}
