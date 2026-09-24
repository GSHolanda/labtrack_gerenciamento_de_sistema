"""Amostras, testes atribuídos e ações do workflow."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import DbSession
from app.api.v1.endpoints._common import Paging, errors, requires
from app.domain.enums import SamplePriority, SampleStatus
from app.domain.permissions import Permission
from app.schemas.common import Page
from app.schemas.samples import (
    AssignTestsRequest,
    ReasonRequest,
    SampleCreate,
    SampleDetail,
    SampleFilter,
    SampleSummary,
    SampleUpdate,
    StatusHistoryRead,
    to_detail,
    to_history,
    to_summary,
)
from app.services.sample_service import SampleService

router = APIRouter(tags=["Samples"])

Reader = requires(Permission.SAMPLE_READ)
Creator = requires(Permission.SAMPLE_CREATE)
Assigner = requires(Permission.SAMPLE_ASSIGN_TESTS)
Analyst = requires(Permission.SAMPLE_ANALYZE)
Canceller = requires(Permission.SAMPLE_CANCEL)


@router.get("/samples", response_model=Page[SampleSummary], responses=errors(401, 403, 422))
def search_samples(
    session: DbSession,
    _: Reader,
    paging: Paging,
    code: Annotated[str | None, Query(max_length=20, examples=["SMP-2026"])] = None,
    product_id: int | None = None,
    client_id: int | None = None,
    lot_number: Annotated[str | None, Query(max_length=50)] = None,
    status_: Annotated[list[SampleStatus] | None, Query(alias="status")] = None,
    priority: SamplePriority | None = None,
    responsible_id: Annotated[int | None, Query(description="Analista responsável")] = None,
    received_from: datetime | None = None,
    received_to: datetime | None = None,
    q: Annotated[
        str | None, Query(max_length=100, description="Código, lote, produto ou cliente")
    ] = None,
) -> Page[SampleSummary]:
    """Pesquisa paginada. `status` aceita vários valores (`?status=RECEIVED&status=IN_ANALYSIS`)."""
    filters = SampleFilter(
        code=code,
        product_id=product_id,
        client_id=client_id,
        lot_number=lot_number,
        statuses=list(status_ or []),
        priority=priority,
        responsible_id=responsible_id,
        received_from=received_from,
        received_to=received_to,
        q=q,
    )
    result = SampleService(session).search(filters, paging)
    return Page.build([to_summary(s) for s in result.items], result.total, result.page, result.size)


@router.post(
    "/samples",
    response_model=SampleDetail,
    status_code=status.HTTP_201_CREATED,
    responses=errors(401, 403, 422),
    summary="Registra amostra",
    description="Gera o código `SMP-AAAA-NNNN` e atribui os testes do plano analítico do produto.",
)
def create_sample(data: SampleCreate, session: DbSession, actor: Creator) -> SampleDetail:
    return to_detail(SampleService(session).create(data, actor))


@router.get("/samples/{sample_id}", response_model=SampleDetail, responses=errors(401, 403, 404))
def get_sample(sample_id: int, session: DbSession, _: Reader) -> SampleDetail:
    return to_detail(SampleService(session).get(sample_id))


@router.patch(
    "/samples/{sample_id}",
    response_model=SampleDetail,
    responses=errors(401, 403, 404, 409, 422),
    summary="Altera dados de registro",
    description="Exige a `version` lida; se outra pessoa alterou antes, retorna 409.",
)
def update_sample(
    sample_id: int, data: SampleUpdate, session: DbSession, actor: Creator
) -> SampleDetail:
    return to_detail(SampleService(session).update(sample_id, data, actor))


@router.post(
    "/samples/{sample_id}/tests",
    response_model=SampleDetail,
    responses=errors(401, 403, 404, 409, 422),
    summary="Atribui testes adicionais",
)
def assign_tests(
    sample_id: int, data: AssignTestsRequest, session: DbSession, actor: Assigner
) -> SampleDetail:
    return to_detail(
        SampleService(session).assign_tests(sample_id, data.test_definition_ids, actor)
    )


@router.post(
    "/sample-tests/{sample_test_id}/cancel",
    response_model=SampleDetail,
    responses=errors(401, 403, 404, 409, 422),
    summary="Cancela teste pendente (exige justificativa)",
)
def cancel_test(
    sample_test_id: int, data: ReasonRequest, session: DbSession, actor: Assigner
) -> SampleDetail:
    return to_detail(SampleService(session).cancel_test(sample_test_id, data.reason, actor))


@router.post(
    "/samples/{sample_id}/start-analysis",
    response_model=SampleDetail,
    responses=errors(401, 403, 404, 409),
    summary="RECEIVED → IN_ANALYSIS",
)
def start_analysis(sample_id: int, session: DbSession, actor: Analyst) -> SampleDetail:
    return to_detail(SampleService(session).start_analysis(sample_id, actor))


@router.post(
    "/samples/{sample_id}/submit-for-review",
    response_model=SampleDetail,
    responses=errors(401, 403, 404, 409),
    summary="IN_ANALYSIS → AWAITING_REVIEW (todos os testes concluídos)",
)
def submit_for_review(sample_id: int, session: DbSession, actor: Analyst) -> SampleDetail:
    return to_detail(SampleService(session).submit_for_review(sample_id, actor))


@router.post(
    "/samples/{sample_id}/cancel",
    response_model=SampleDetail,
    responses=errors(401, 403, 404, 409, 422),
    summary="Cancela a amostra (exige justificativa)",
)
def cancel_sample(
    sample_id: int, data: ReasonRequest, session: DbSession, actor: Canceller
) -> SampleDetail:
    return to_detail(SampleService(session).cancel(sample_id, data.reason, actor))


@router.get(
    "/samples/{sample_id}/status-history",
    response_model=list[StatusHistoryRead],
    responses=errors(401, 403, 404),
)
def status_history(sample_id: int, session: DbSession, _: Reader) -> list[StatusHistoryRead]:
    return [to_history(entry) for entry in SampleService(session).status_history(sample_id)]
