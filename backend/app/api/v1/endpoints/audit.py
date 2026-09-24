"""Consultas somente leitura do audit trail e verificação de integridade."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.api.v1.endpoints._common import Paging, errors, requires
from app.domain.audit import AuditAction
from app.domain.enums import ActorType
from app.domain.permissions import Permission
from app.schemas.audit import AuditFilter, AuditRead, AuditVerificationRead
from app.schemas.common import Page
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit-logs", tags=["Audit Trail"])
Reader = requires(Permission.AUDIT_READ)


@router.get("", response_model=Page[AuditRead], responses=errors(401, 403, 422))
def search_audit_logs(
    session: DbSession,
    _: Reader,
    paging: Paging,
    user_id: Annotated[int | None, Query(gt=0)] = None,
    instrument_id: Annotated[int | None, Query(gt=0)] = None,
    actor_type: ActorType | None = None,
    action: AuditAction | None = None,
    entity_type: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
    entity_id: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
    sample_id: Annotated[int | None, Query(gt=0)] = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
) -> Page[AuditRead]:
    """Filtros combinados por AND; datas inclusivas. Ordenação padrão: mais recentes."""
    result = AuditService(session).search(
        AuditFilter(
            user_id=user_id,
            instrument_id=instrument_id,
            actor_type=actor_type,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            sample_id=sample_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
        ),
        paging,
    )
    return Page.build(
        [AuditRead.model_validate(item) for item in result.items],
        result.total,
        result.page,
        result.size,
    )


@router.get("/verify", response_model=AuditVerificationRead, responses=errors(401, 403))
def verify_audit_logs(session: DbSession, _: Reader) -> AuditVerificationRead:
    """Verifica toda a cadeia em ordem de ID e aponta a primeira inconsistência.

    Não certifica integridade regulatória nem detecta remoção da cauda ou
    recálculo completo da cadeia sem uma âncora externa confiável.
    """
    return AuditVerificationRead.model_validate(AuditService(session).verify())
