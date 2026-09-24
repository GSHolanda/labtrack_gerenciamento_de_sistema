"""Contrato do relatório da amostra (a mesma estrutura alimenta o JSON e o PDF)."""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums import (
    ResultSource,
    SampleOrigin,
    SamplePriority,
    SampleStatus,
    SampleTestStatus,
    SpecStatus,
)
from app.schemas.common import UserReference

# Campos cobertos pela impressão digital: o conteúdo analítico, sem os dados da emissão.
FINGERPRINT_FIELDS = frozenset({"sample", "decision", "tests"})


class ReportParty(BaseModel):
    code: str
    name: str


class ReportProduct(ReportParty):
    category: str | None


class ReportSample(BaseModel):
    id: int
    sample_code: str
    status: SampleStatus
    client: ReportParty
    product: ReportProduct
    lot_number: str
    origin: SampleOrigin
    priority: SamplePriority
    received_at: datetime
    registered_by: UserReference
    responsible: UserReference | None = Field(description="Analista responsável")
    submitted_at: datetime | None = Field(description="Envio para revisão")
    notes: str | None


class ReportDecision(BaseModel):
    status: SampleStatus = Field(description="APPROVED ou REJECTED")
    reviewed_by: UserReference
    reviewed_at: datetime
    comment: str | None = Field(
        description="Comentário da aprovação ou justificativa da reprovação"
    )


class ReportResult(BaseModel):
    version: int
    value: Decimal
    unit: str
    spec_status: SpecStatus
    source: ResultSource
    entered_by: UserReference | None
    instrument_code: str | None
    entered_at: datetime
    change_reason: str | None = Field(description="Justificativa da correção (versão ≥ 2)")
    comment: str | None


class ReportCancellation(BaseModel):
    cancelled_by: str
    cancelled_at: datetime
    reason: str | None


class ReportTest(BaseModel):
    test_code: str
    test_name: str
    method: str
    unit: str
    decimal_places: int
    spec_min: Decimal | None
    spec_max: Decimal | None
    status: SampleTestStatus
    result: ReportResult | None = Field(description="Resultado vigente")
    previous_versions: list[ReportResult] = Field(
        description="Versões substituídas por correção, da mais antiga para a mais recente"
    )
    had_oos: bool = Field(description="Alguma versão, mesmo corrigida, ficou fora da especificação")
    cancellation: ReportCancellation | None


class ReportSummary(BaseModel):
    tests_reported: int = Field(description="Testes com resultado")
    tests_cancelled: int
    corrected_tests: int = Field(description="Testes com resultado corrigido")
    current_oos: int = Field(description="Resultados vigentes fora da especificação")
    had_oos: bool = Field(description="Houve OOS em alguma versão de algum teste")


class SampleReport(BaseModel):
    lab_name: str
    generated_at: datetime
    generated_by: UserReference
    timezone: str = Field(description="Fuso do laboratório usado no PDF")
    content_hash: str = Field(
        description="SHA-256 do conteúdo (amostra, decisão e testes). Igual em todas as "
        "emissões da mesma amostra; o PDF e o audit trail registram o mesmo valor."
    )
    sample: ReportSample
    decision: ReportDecision
    tests: list[ReportTest]
    summary: ReportSummary
    analysts: list[UserReference] = Field(description="Quem lançou resultados")
    instruments: list[str] = Field(description="Equipamentos que enviaram resultados")


# --- Conversão das entidades (duck typing: schemas não importam modelos) -------


def _user_ref(user: Any) -> UserReference | None:
    return UserReference(id=user.id, full_name=user.full_name) if user else None


def _result(result: Any) -> ReportResult:
    return ReportResult(
        version=result.version,
        value=result.value,
        unit=result.unit,
        spec_status=result.spec_status,
        source=result.source,
        entered_by=_user_ref(result.entered_by),
        instrument_code=result.instrument.code if result.instrument else None,
        entered_at=result.entered_at,
        change_reason=result.change_reason,
        comment=result.comment,
    )


def _test(test: Any, cancellation: Any) -> ReportTest:
    definition = test.test_definition
    versions = sorted(test.results, key=lambda result: result.version)
    current = next((result for result in versions if result.is_current), None)
    return ReportTest(
        test_code=definition.code,
        test_name=definition.name,
        method=definition.method,
        unit=test.unit,
        decimal_places=definition.decimal_places,
        spec_min=test.spec_min,
        spec_max=test.spec_max,
        status=test.status,
        result=_result(current) if current else None,
        previous_versions=[_result(result) for result in versions if not result.is_current],
        had_oos=any(result.spec_status == SpecStatus.OOS for result in versions),
        cancellation=ReportCancellation(
            cancelled_by=cancellation.actor_name,
            cancelled_at=cancellation.occurred_at,
            reason=cancellation.reason,
        )
        if cancellation is not None
        else None,
    )


def fingerprint_content(body: Mapping[str, Any]) -> dict[str, Any]:
    """Parte do conteúdo coberta pela impressão digital, como dados simples."""

    def plain(value: Any) -> Any:
        if isinstance(value, BaseModel):
            return value.model_dump()
        if isinstance(value, list):
            return [plain(item) for item in value]
        return value

    return {key: plain(body[key]) for key in sorted(FINGERPRINT_FIELDS)}


def to_report_body(sample: Any, cancellations: Mapping[int, Any]) -> dict[str, Any]:
    """Conteúdo do relatório a partir da amostra carregada com testes e resultados."""
    tests = [_test(test, cancellations.get(test.id)) for test in sample.tests]
    analysts: dict[int, UserReference] = {}
    instruments: set[str] = set()
    for test in tests:
        for result in [*test.previous_versions, *([test.result] if test.result else [])]:
            if result.entered_by is not None:
                analysts.setdefault(result.entered_by.id, result.entered_by)
            if result.instrument_code:
                instruments.add(result.instrument_code)

    return {
        "sample": ReportSample(
            id=sample.id,
            sample_code=sample.sample_code,
            status=sample.status,
            client=ReportParty(code=sample.client.code, name=sample.client.name),
            product=ReportProduct(
                code=sample.product.code,
                name=sample.product.name,
                category=sample.product.category,
            ),
            lot_number=sample.lot_number,
            origin=sample.origin,
            priority=sample.priority,
            received_at=sample.received_at,
            registered_by=_user_ref(sample.created_by),
            responsible=_user_ref(sample.responsible),
            submitted_at=sample.submitted_at,
            notes=sample.notes,
        ),
        "decision": ReportDecision(
            status=sample.status,
            reviewed_by=_user_ref(sample.reviewed_by),
            reviewed_at=sample.reviewed_at,
            comment=sample.review_comment,
        ),
        "tests": tests,
        "summary": ReportSummary(
            tests_reported=sum(test.result is not None for test in tests),
            tests_cancelled=sum(test.status == SampleTestStatus.CANCELLED for test in tests),
            corrected_tests=sum(bool(test.previous_versions) for test in tests),
            current_oos=sum(
                test.status != SampleTestStatus.CANCELLED
                and test.result is not None
                and test.result.spec_status == SpecStatus.OOS
                for test in tests
            ),
            had_oos=any(test.had_oos for test in tests),
        ),
        "analysts": sorted(analysts.values(), key=lambda user: user.full_name),
        "instruments": sorted(instruments),
    }
