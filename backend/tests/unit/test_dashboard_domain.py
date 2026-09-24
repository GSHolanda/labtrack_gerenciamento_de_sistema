from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from zoneinfo import ZoneInfo

import pytest

from app.domain.dashboard import (
    Granularity,
    Window,
    approval_rate,
    bucket_of,
    buckets_for,
    granularity_for,
    processing_time,
)

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


@pytest.mark.parametrize(
    ("days", "expected"),
    [(1, "day"), (31, "day"), (32, "week"), (120, "week"), (121, "month"), (366, "month")],
)
def test_granularity_keeps_a_readable_number_of_points(days: int, expected: str) -> None:
    assert granularity_for(days) == expected


def test_buckets_use_the_laboratory_timezone() -> None:
    # 23:30 de 30/09 em São Paulo ainda é setembro, embora já seja outubro em UTC.
    moment = datetime(2026, 10, 1, 2, 30, tzinfo=UTC)
    assert bucket_of(moment, Granularity.DAY, SAO_PAULO) == date(2026, 9, 30)
    assert bucket_of(moment, Granularity.WEEK, SAO_PAULO) == date(2026, 9, 28)  # segunda
    assert bucket_of(moment, Granularity.MONTH, SAO_PAULO) == date(2026, 9, 1)
    assert bucket_of(moment, Granularity.MONTH, UTC) == date(2026, 10, 1)


def test_naive_datetimes_are_treated_as_utc() -> None:
    assert bucket_of(datetime(2026, 10, 1, 2, 30), Granularity.DAY, SAO_PAULO) == date(2026, 9, 30)


def test_buckets_cover_the_window_without_gaps() -> None:
    now = datetime(2026, 9, 24, 15, 0, tzinfo=UTC)
    daily = buckets_for(Window.last_days(30, now), Granularity.DAY, SAO_PAULO)
    assert daily[0] == date(2026, 8, 25)
    assert daily[-1] == date(2026, 9, 24)
    assert all(b - a == timedelta(days=1) for a, b in pairwise(daily))

    weekly = buckets_for(Window.last_days(90, now), Granularity.WEEK, SAO_PAULO)
    assert all(bucket.weekday() == 0 for bucket in weekly)
    assert weekly[-1] == date(2026, 9, 21)

    monthly = buckets_for(Window.last_days(365, now), Granularity.MONTH, SAO_PAULO)
    assert monthly[0] == date(2025, 9, 1)
    assert monthly[-1] == date(2026, 9, 1)
    assert len(monthly) == 13
    assert date(2026, 1, 1) in monthly  # virada de ano


def test_previous_window_is_adjacent_and_equal() -> None:
    window = Window.last_days(30, datetime(2026, 9, 24, tzinfo=UTC))
    previous = window.previous()
    assert previous.end == window.start
    assert previous.end - previous.start == window.end - window.start
    assert window.contains(window.start)
    assert not window.contains(window.end)


def test_approval_rate_counts_only_decided_samples() -> None:
    assert approval_rate(0, 0) is None
    assert approval_rate(3, 1) == 0.75
    assert approval_rate(2, 1) == 0.6667


def test_processing_time_average_and_median() -> None:
    durations = [timedelta(hours=2), timedelta(hours=4), timedelta(hours=30)]
    time = processing_time(durations)
    assert (time.average_hours, time.median_hours, time.samples) == (12.0, 4.0, 3)
    assert processing_time([]).average_hours is None
