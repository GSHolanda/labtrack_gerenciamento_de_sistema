"""Resultados analíticos: lançamento, histórico de versões e pesquisa (inclusive OOS)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import DbSession
from app.api.v1.endpoints._common import Paging, errors, requires
from app.domain.enums import ResultSource, SpecStatus
from app.domain.permissions import Permission
from app.schemas.common import Page
from app.schemas.results import (
    ResultEntry,
    ResultFilter,
    ResultListItem,
    ResultRead,
    to_result,
    to_result_item,
)
from app.services.result_service import ResultService

router = APIRouter(tags=["Results"])

Reader = requires(Permission.SAMPLE_READ)
Enterer = requires(Permission.RESULT_ENTER)


@router.post(
    "/sample-tests/{sample_test_id}/results",
    response_model=ResultRead,
    status_code=status.HTTP_201_CREATED,
    responses=errors(401, 403, 404, 409, 422),
    summary="Registra resultado (ou corrige, criando nova versão)",
    description=(
        "O valor é comparado automaticamente com os limites do teste e classificado como "
        "`IN_SPEC` ou `OOS`. Se o teste já tiver resultado, `change_reason` é obrigatória e a "
        "versão anterior é preservada."
    ),
)
def enter_result(
    sample_test_id: int, data: ResultEntry, session: DbSession, actor: Enterer
) -> ResultRead:
    return to_result(ResultService(session).enter_manual(sample_test_id, data, actor))


@router.get(
    "/sample-tests/{sample_test_id}/results",
    response_model=list[ResultRead],
    responses=errors(401, 403, 404),
    summary="Todas as versões do resultado de um teste",
)
def result_history(sample_test_id: int, session: DbSession, _: Reader) -> list[ResultRead]:
    return [to_result(result) for result in ResultService(session).history(sample_test_id)]


@router.get(
    "/results",
    response_model=Page[ResultListItem],
    responses=errors(401, 403, 422),
    summary="Pesquisa de resultados",
    description="Use `spec_status=OOS` para listar resultados fora da especificação.",
)
def search_results(
    session: DbSession,
    _: Reader,
    paging: Paging,
    spec_status: SpecStatus | None = None,
    source: ResultSource | None = None,
    test_code: Annotated[str | None, Query(max_length=30)] = None,
    sample_code: Annotated[str | None, Query(max_length=20)] = None,
    entered_from: datetime | None = None,
    entered_to: datetime | None = None,
    current_only: Annotated[
        bool, Query(description="Somente versões vigentes (false inclui corrigidas)")
    ] = True,
) -> Page[ResultListItem]:
    filters = ResultFilter(
        spec_status=spec_status,
        source=source,
        test_code=test_code,
        sample_code=sample_code,
        entered_from=entered_from,
        entered_to=entered_to,
        current_only=current_only,
    )
    result = ResultService(session).search(filters, paging)
    return Page.build(
        [to_result_item(item) for item in result.items], result.total, result.page, result.size
    )
