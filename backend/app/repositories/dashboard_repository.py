"""Consultas agregadas do dashboard (contagens no banco; nenhuma linha a mais que o necessário)."""

from datetime import datetime
from typing import NamedTuple

from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session

from app.domain.enums import SamplePriority, SampleStatus, SampleTestStatus, SpecStatus
from app.models import Sample, SampleTest, TestDefinition, TestResult

OPEN_STATUSES = (SampleStatus.RECEIVED, SampleStatus.IN_ANALYSIS, SampleStatus.AWAITING_REVIEW)
FINAL_STATUSES = (SampleStatus.APPROVED, SampleStatus.REJECTED, SampleStatus.CANCELLED)


class CompletedSample(NamedTuple):
    status: str
    received_at: datetime
    completed_at: datetime


class ResultsByTest(NamedTuple):
    code: str
    name: str
    results: int
    oos: int


class DashboardRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def status_counts(
        self, *, received_from: datetime | None = None, received_to: datetime | None = None
    ) -> dict[str, int]:
        statement = select(Sample.status, func.count()).group_by(Sample.status)
        if received_from is not None:
            statement = statement.where(Sample.received_at >= received_from)
        if received_to is not None:
            statement = statement.where(Sample.received_at < received_to)
        return {status: total for status, total in self.session.execute(statement)}

    def urgent_open(self) -> int:
        return self._count(
            select(func.count()).where(
                Sample.status.in_(OPEN_STATUSES), Sample.priority == SamplePriority.URGENT
            )
        )

    def open_with_current_oos(self) -> int:
        """Amostras em aberto com resultado vigente OOS: não podem ser aprovadas."""
        return self._count(
            select(func.count(distinct(Sample.id)))
            .select_from(Sample)
            .join(SampleTest, SampleTest.sample_id == Sample.id)
            .join(TestResult, TestResult.sample_test_id == SampleTest.id)
            .where(
                Sample.status.in_(OPEN_STATUSES),
                SampleTest.status != SampleTestStatus.CANCELLED,
                TestResult.is_current.is_(True),
                TestResult.spec_status == SpecStatus.OOS,
            )
        )

    def completed(self, start: datetime, end: datetime) -> list[CompletedSample]:
        """Amostras finalizadas no período: só status e datas (base de taxas e tempos)."""
        rows = self.session.execute(
            select(Sample.status, Sample.received_at, Sample.completed_at).where(
                Sample.status.in_(FINAL_STATUSES),
                Sample.completed_at >= start,
                Sample.completed_at < end,
            )
        )
        return [CompletedSample(*row) for row in rows]

    def oos_totals(self, start: datetime, end: datetime) -> tuple[int, int]:
        """Resultados OOS registrados no período (todas as versões) e amostras afetadas.

        Conta também versões depois corrigidas: um OOS nunca some da estatística.
        """
        row = self.session.execute(
            select(func.count(TestResult.id), func.count(distinct(SampleTest.sample_id)))
            .select_from(TestResult)
            .join(SampleTest, SampleTest.id == TestResult.sample_test_id)
            .where(
                TestResult.spec_status == SpecStatus.OOS,
                TestResult.entered_at >= start,
                TestResult.entered_at < end,
            )
        ).one()
        return row[0], row[1]

    def results_by_test(self, start: datetime, end: datetime) -> list[ResultsByTest]:
        """Resultados registrados no período por tipo de teste, com quantos foram OOS."""
        total = func.count(TestResult.id)
        oos = func.sum(case((TestResult.spec_status == SpecStatus.OOS, 1), else_=0))
        rows = self.session.execute(
            select(TestDefinition.code, TestDefinition.name, total, oos)
            .select_from(TestResult)
            .join(SampleTest, SampleTest.id == TestResult.sample_test_id)
            .join(TestDefinition, TestDefinition.id == SampleTest.test_definition_id)
            .where(TestResult.entered_at >= start, TestResult.entered_at < end)
            .group_by(TestDefinition.code, TestDefinition.name)
            .order_by(oos.desc(), total.desc(), TestDefinition.code)
        )
        return [ResultsByTest(code, name, results, oos or 0) for code, name, results, oos in rows]

    def _count(self, statement) -> int:  # type: ignore[no-untyped-def]
        return self.session.scalar(statement) or 0
