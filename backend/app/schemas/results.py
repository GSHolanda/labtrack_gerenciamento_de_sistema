"""Contratos de resultados analíticos e da revisão."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.domain.enums import ResultSource, SpecStatus
from app.schemas.common import UserReference

Comment = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=1000)]


class ResultEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Annotated[Decimal, Field(max_digits=14, decimal_places=4, examples=[7.21])]
    comment: Comment | None = None
    change_reason: Reason | None = Field(
        default=None,
        description="Obrigatória quando o teste já tem resultado (correção gera nova versão)",
        examples=["Erro de transcrição"],
    )


class ApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, description="Senha do revisor (confirmação da assinatura)")
    comment: Comment | None = None


@dataclass(frozen=True)
class ResultFilter:
    spec_status: str | None = None
    source: str | None = None
    test_code: str | None = None
    sample_code: str | None = None
    entered_from: datetime | None = None
    entered_to: datetime | None = None
    current_only: bool = True


class ResultRead(BaseModel):
    id: int
    sample_test_id: int
    value: Decimal
    unit: str
    spec_status: SpecStatus
    source: ResultSource
    version: int
    is_current: bool
    entered_by: UserReference | None
    instrument_code: str | None
    entered_at: datetime
    change_reason: str | None
    comment: str | None


class ResultListItem(ResultRead):
    sample_id: int
    sample_code: str
    test_code: str
    test_name: str
    spec_min: Decimal | None
    spec_max: Decimal | None


def to_result(result: Any) -> ResultRead:
    return ResultRead(**_result_fields(result))


def to_result_item(result: Any) -> ResultListItem:
    sample_test = result.sample_test
    return ResultListItem(
        **_result_fields(result),
        sample_id=sample_test.sample.id,
        sample_code=sample_test.sample.sample_code,
        test_code=sample_test.test_definition.code,
        test_name=sample_test.test_definition.name,
        spec_min=sample_test.spec_min,
        spec_max=sample_test.spec_max,
    )


def _result_fields(result: Any) -> dict[str, Any]:
    entered_by = result.entered_by
    return {
        "id": result.id,
        "sample_test_id": result.sample_test_id,
        "value": result.value,
        "unit": result.unit,
        "spec_status": result.spec_status,
        "source": result.source,
        "version": result.version,
        "is_current": result.is_current,
        "entered_by": UserReference(id=entered_by.id, full_name=entered_by.full_name)
        if entered_by
        else None,
        "instrument_code": result.instrument.code if result.instrument else None,
        "entered_at": result.entered_at,
        "change_reason": result.change_reason,
        "comment": result.comment,
    }
