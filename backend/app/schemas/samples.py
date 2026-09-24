"""Contratos de amostras, testes atribuídos e workflow."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.domain.enums import SampleOrigin, SamplePriority, SampleStatus, SampleTestStatus
from app.domain.workflow import SampleAction, allowed_actions

LotNumber = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=1000)]


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class SampleFilter:
    code: str | None = None
    product_id: int | None = None
    client_id: int | None = None
    lot_number: str | None = None
    statuses: list[str] = field(default_factory=list)
    priority: str | None = None
    responsible_id: int | None = None
    received_from: datetime | None = None
    received_to: datetime | None = None
    q: str | None = None


class SampleCreate(_Input):
    product_id: int
    client_id: int
    lot_number: LotNumber = Field(examples=["L2026-0915"])
    origin: SampleOrigin
    received_at: datetime = Field(description="Data e hora de recebimento (com fuso horário)")
    priority: SamplePriority = SamplePriority.NORMAL
    responsible_id: int | None = Field(default=None, description="Analista responsável")
    notes: Annotated[str, StringConstraints(max_length=2000)] | None = None


class SampleUpdate(_Input):
    version: int = Field(description="Versão lida pelo cliente (controle de concorrência)")
    lot_number: LotNumber | None = None
    origin: SampleOrigin | None = None
    priority: SamplePriority | None = None
    responsible_id: int | None = None
    notes: Annotated[str, StringConstraints(max_length=2000)] | None = None


class AssignTestsRequest(_Input):
    test_definition_ids: list[int] = Field(min_length=1, max_length=50)


class ReasonRequest(_Input):
    reason: Reason = Field(examples=["Amostra registrada em duplicidade"])


class Reference(BaseModel):
    id: int
    code: str
    name: str


class UserReference(BaseModel):
    id: int
    full_name: str


class SampleSummary(BaseModel):
    id: int
    sample_code: str
    product: Reference
    client: Reference
    lot_number: str
    origin: SampleOrigin
    received_at: datetime
    priority: SamplePriority
    status: SampleStatus
    responsible: UserReference | None
    version: int
    created_at: datetime


class SampleTestRead(BaseModel):
    id: int
    test_definition_id: int
    test_code: str
    test_name: str
    method: str
    unit: str
    spec_min: Decimal | None
    spec_max: Decimal | None
    status: SampleTestStatus
    assigned_at: datetime


class SampleDetail(SampleSummary):
    notes: str | None
    created_by: UserReference
    submitted_at: datetime | None
    reviewed_by: UserReference | None
    reviewed_at: datetime | None
    review_comment: str | None
    completed_at: datetime | None
    tests: list[SampleTestRead]
    allowed_actions: list[SampleAction]


class StatusHistoryRead(BaseModel):
    from_status: SampleStatus | None
    to_status: SampleStatus
    changed_by: UserReference
    changed_at: datetime
    reason: str | None


# --- Conversão das entidades (duck typing: schemas não importam modelos) -------


def _user_ref(user: Any) -> UserReference | None:
    return UserReference(id=user.id, full_name=user.full_name) if user else None


def _summary_fields(sample: Any) -> dict[str, Any]:
    return {
        "id": sample.id,
        "sample_code": sample.sample_code,
        "product": Reference(
            id=sample.product.id, code=sample.product.code, name=sample.product.name
        ),
        "client": Reference(id=sample.client.id, code=sample.client.code, name=sample.client.name),
        "lot_number": sample.lot_number,
        "origin": sample.origin,
        "received_at": sample.received_at,
        "priority": sample.priority,
        "status": sample.status,
        "responsible": _user_ref(sample.responsible),
        "version": sample.version,
        "created_at": sample.created_at,
    }


def to_summary(sample: Any) -> SampleSummary:
    return SampleSummary(**_summary_fields(sample))


def to_sample_test(test: Any) -> SampleTestRead:
    definition = test.test_definition
    return SampleTestRead(
        id=test.id,
        test_definition_id=definition.id,
        test_code=definition.code,
        test_name=definition.name,
        method=definition.method,
        unit=test.unit,
        spec_min=test.spec_min,
        spec_max=test.spec_max,
        status=test.status,
        assigned_at=test.assigned_at,
    )


def to_detail(sample: Any) -> SampleDetail:
    return SampleDetail(
        **_summary_fields(sample),
        notes=sample.notes,
        created_by=_user_ref(sample.created_by),
        submitted_at=sample.submitted_at,
        reviewed_by=_user_ref(sample.reviewed_by),
        reviewed_at=sample.reviewed_at,
        review_comment=sample.review_comment,
        completed_at=sample.completed_at,
        tests=[to_sample_test(test) for test in sample.tests],
        allowed_actions=allowed_actions(sample.status),
    )


def to_history(entry: Any) -> StatusHistoryRead:
    return StatusHistoryRead(
        from_status=entry.from_status,
        to_status=entry.to_status,
        changed_by=_user_ref(entry.changed_by),
        changed_at=entry.changed_at,
        reason=entry.reason,
    )
