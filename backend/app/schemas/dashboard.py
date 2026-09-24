"""Contratos do dashboard: indicadores e séries para gráficos."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.domain.dashboard import Granularity
from app.domain.enums import SampleStatus


class Period(BaseModel):
    days: int
    start: datetime = Field(description="Início do período (inclusivo, UTC)")
    end: datetime = Field(description="Fim do período (exclusivo, UTC): o momento da consulta")
    timezone: str = Field(description="Fuso do laboratório usado para agrupar dias e meses")


class Workload(BaseModel):
    """Situação atual, independente do período."""

    open: int = Field(description="Amostras não finalizadas (recebidas, em análise, em revisão)")
    received: int
    in_analysis: int
    awaiting_review: int
    open_with_oos: int = Field(description="Em aberto com resultado vigente OOS")
    urgent_open: int


class PeriodTotals(BaseModel):
    received: int = Field(description="Amostras recebidas no período")
    approved: int = Field(description="Aprovadas no período (data da decisão)")
    rejected: int
    cancelled: int
    approval_rate: float | None = Field(
        description="Aprovadas / (aprovadas + reprovadas); vazio sem decisões"
    )
    average_processing_hours: float | None = Field(
        description="Média do recebimento à decisão (aprovação ou reprovação)"
    )
    median_processing_hours: float | None
    oos_results: int = Field(description="Resultados OOS registrados (inclui versões corrigidas)")
    samples_with_oos: int


class DashboardSummary(BaseModel):
    generated_at: datetime
    period: Period
    workload: Workload
    current: PeriodTotals
    previous: PeriodTotals = Field(description="Período anterior de mesma duração")


class ThroughputPoint(BaseModel):
    bucket: date = Field(description="Primeiro dia (local) do dia, semana ou mês")
    approved: int
    rejected: int
    approval_rate: float | None


class StatusCount(BaseModel):
    status: SampleStatus
    count: int


class TestOos(BaseModel):
    __test__ = False

    test_code: str
    test_name: str
    results: int
    oos: int
    oos_rate: float


class DashboardCharts(BaseModel):
    generated_at: datetime
    period: Period
    granularity: Granularity
    throughput: list[ThroughputPoint] = Field(description="Decisões por intervalo, sem lacunas")
    by_status: list[StatusCount] = Field(description="Amostras recebidas no período, status atual")
    oos_by_test: list[TestOos] = Field(description="Resultados do período por teste")
