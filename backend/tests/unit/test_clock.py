from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.core.clock import frozen_at, utcnow, utctoday


def test_real_clock_by_default() -> None:
    before = datetime.now(UTC)
    assert before <= utcnow() <= datetime.now(UTC)


def test_frozen_clock_is_restored_even_when_nested() -> None:
    first = datetime(2026, 8, 1, 9, 30, tzinfo=UTC)
    brasilia = timezone(timedelta(hours=-3))
    with frozen_at(first):
        assert utcnow() == first
        with frozen_at(datetime(2026, 8, 1, 22, 0, tzinfo=brasilia)):
            assert utcnow() == datetime(2026, 8, 2, 1, 0, tzinfo=UTC)
            assert utctoday().isoformat() == "2026-08-02"
        assert utcnow() == first
    assert utcnow() != first


def test_frozen_clock_requires_timezone() -> None:
    with pytest.raises(ValueError, match="fuso"), frozen_at(datetime(2026, 8, 1)):
        pass
