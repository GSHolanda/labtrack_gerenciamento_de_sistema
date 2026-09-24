"""Indicadores do dashboard (ETAPA 10): carga de trabalho, decisões, tempos e OOS."""

from collections import Counter
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.domain.dashboard import (
    Window,
    approval_rate,
    as_utc,
    bucket_of,
    buckets_for,
    granularity_for,
    processing_time,
)
from app.domain.enums import SampleStatus
from app.repositories.dashboard_repository import OPEN_STATUSES, DashboardRepository
from app.schemas.dashboard import (
    DashboardCharts,
    DashboardSummary,
    Period,
    PeriodTotals,
    StatusCount,
    TestOos,
    ThroughputPoint,
    Workload,
)

DECIDED = (SampleStatus.APPROVED, SampleStatus.REJECTED)


class DashboardService:
    def __init__(self, session: Session, timezone: str) -> None:
        self.repository = DashboardRepository(session)
        self.timezone = timezone
        self.tz = ZoneInfo(timezone)

    def summary(self, period_days: int, now: datetime | None = None) -> DashboardSummary:
        window = Window.last_days(period_days, now or utcnow())
        counts = self.repository.status_counts()
        workload = Workload(
            open=sum(counts.get(status, 0) for status in OPEN_STATUSES),
            received=counts.get(SampleStatus.RECEIVED, 0),
            in_analysis=counts.get(SampleStatus.IN_ANALYSIS, 0),
            awaiting_review=counts.get(SampleStatus.AWAITING_REVIEW, 0),
            open_with_oos=self.repository.open_with_current_oos(),
            urgent_open=self.repository.urgent_open(),
        )
        return DashboardSummary(
            generated_at=window.end,
            period=self._period(period_days, window),
            workload=workload,
            current=self._totals(window),
            previous=self._totals(window.previous()),
        )

    def charts(self, period_days: int, now: datetime | None = None) -> DashboardCharts:
        window = Window.last_days(period_days, now or utcnow())
        granularity = granularity_for(period_days)

        decisions: dict[date, Counter[str]] = {
            bucket: Counter() for bucket in buckets_for(window, granularity, self.tz)
        }
        for sample in self.repository.completed(window.start, window.end):
            if sample.status in DECIDED:
                decisions[bucket_of(sample.completed_at, granularity, self.tz)][sample.status] += 1
        throughput = [
            ThroughputPoint(
                bucket=bucket,
                approved=counts[SampleStatus.APPROVED],
                rejected=counts[SampleStatus.REJECTED],
                approval_rate=approval_rate(
                    counts[SampleStatus.APPROVED], counts[SampleStatus.REJECTED]
                ),
            )
            for bucket, counts in decisions.items()
        ]

        received = self.repository.status_counts(received_from=window.start, received_to=window.end)
        return DashboardCharts(
            generated_at=window.end,
            period=self._period(period_days, window),
            granularity=granularity,
            throughput=throughput,
            by_status=[
                StatusCount(status=status, count=received.get(status, 0)) for status in SampleStatus
            ],
            oos_by_test=[
                TestOos(
                    test_code=row.code,
                    test_name=row.name,
                    results=row.results,
                    oos=row.oos,
                    oos_rate=round(row.oos / row.results, 4),
                )
                for row in self.repository.results_by_test(window.start, window.end)
            ],
        )

    def _totals(self, window: Window) -> PeriodTotals:
        completed = self.repository.completed(window.start, window.end)
        by_status = Counter(sample.status for sample in completed)
        decided = [sample for sample in completed if sample.status in DECIDED]
        time = processing_time(
            [as_utc(sample.completed_at) - as_utc(sample.received_at) for sample in decided]
        )
        oos_results, samples_with_oos = self.repository.oos_totals(window.start, window.end)
        received = self.repository.status_counts(received_from=window.start, received_to=window.end)
        approved = by_status[SampleStatus.APPROVED]
        rejected = by_status[SampleStatus.REJECTED]
        return PeriodTotals(
            received=sum(received.values()),
            approved=approved,
            rejected=rejected,
            cancelled=by_status[SampleStatus.CANCELLED],
            approval_rate=approval_rate(approved, rejected),
            average_processing_hours=time.average_hours,
            median_processing_hours=time.median_hours,
            oos_results=oos_results,
            samples_with_oos=samples_with_oos,
        )

    def _period(self, days: int, window: Window) -> Period:
        return Period(days=days, start=window.start, end=window.end, timezone=self.timezone)
