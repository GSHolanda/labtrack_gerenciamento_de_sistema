"""Dashboard: indicadores e séries (todos os perfis com DASHBOARD_VIEW)."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AppSettings, DbSession
from app.api.v1.endpoints._common import errors, requires
from app.domain.permissions import Permission
from app.schemas.dashboard import DashboardCharts, DashboardSummary
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
Viewer = requires(Permission.DASHBOARD_VIEW)
PeriodDays = Annotated[
    int, Query(ge=1, le=366, description="Últimos N dias, até o momento da consulta")
]


@router.get(
    "/summary",
    response_model=DashboardSummary,
    responses=errors(401, 403),
    summary="Indicadores: carga atual e resultados do período",
    description=(
        "`workload` é a situação atual (independe do período). `current` e `previous` "
        "comparam o período com o anterior de mesma duração."
    ),
)
def summary(
    session: DbSession, settings: AppSettings, _: Viewer, period_days: PeriodDays = 30
) -> DashboardSummary:
    return DashboardService(session, settings.lab_timezone).summary(period_days)


@router.get(
    "/charts",
    response_model=DashboardCharts,
    responses=errors(401, 403),
    summary="Séries para gráficos: decisões, status e OOS por teste",
    description=(
        "A série de decisões é diária até 31 dias, semanal até 120 e mensal acima disso, "
        "agrupada no fuso do laboratório e sem lacunas."
    ),
)
def charts(
    session: DbSession, settings: AppSettings, _: Viewer, period_days: PeriodDays = 30
) -> DashboardCharts:
    return DashboardService(session, settings.lab_timezone).charts(period_days)
