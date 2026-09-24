from datetime import UTC, date, datetime, timedelta

import pytest

from app.core.exceptions import BusinessRuleError, ConflictError
from app.domain.instruments import (
    ONLINE_WINDOW,
    calibration_is_valid,
    ensure_can_measure,
    ensure_compatible,
    ensure_unit,
    is_online,
)

TODAY = date(2026, 9, 24)
NOW = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("due_date", "valid"),
    [(TODAY + timedelta(days=1), True), (TODAY, True), (TODAY - timedelta(days=1), False)],
)
def test_calibration_is_valid_until_due_date_inclusive(due_date: date, valid: bool) -> None:
    assert calibration_is_valid(due_date, TODAY) is valid


def test_missing_calibration_is_not_valid() -> None:
    assert calibration_is_valid(None, TODAY) is False


@pytest.mark.parametrize(
    ("last", "online"),
    [
        (None, False),
        (NOW - ONLINE_WINDOW, True),
        (NOW - ONLINE_WINDOW - timedelta(seconds=1), False),
        ((NOW - timedelta(minutes=1)).replace(tzinfo=None), True),  # SQLite: sem fuso
    ],
)
def test_online_window(last: datetime | None, online: bool) -> None:
    assert is_online(last, NOW) is online


def test_only_active_and_calibrated_instruments_measure() -> None:
    ensure_can_measure("PH-01", "ACTIVE", TODAY, TODAY)
    for status in ("MAINTENANCE", "INACTIVE"):
        with pytest.raises(ConflictError) as exc:
            ensure_can_measure("PH-01", status, TODAY, TODAY)
        assert exc.value.code == "INSTRUMENT_NOT_ACTIVE"


@pytest.mark.parametrize(
    ("due_date", "fragment"),
    [(TODAY - timedelta(days=1), "venceu em 23/09/2026"), (None, "não tem calibração")],
)
def test_expired_or_missing_calibration_blocks_measurement(
    due_date: date | None, fragment: str
) -> None:
    with pytest.raises(ConflictError) as exc:
        ensure_can_measure("PH-01", "ACTIVE", due_date, TODAY)
    assert exc.value.code == "CALIBRATION_EXPIRED"
    assert fragment in exc.value.message


@pytest.mark.parametrize("required", ["DENSITY_METER", None])
def test_instrument_type_must_match_the_test(required: str | None) -> None:
    ensure_compatible("PH-01", "PH_METER", "PH", "PH_METER")
    with pytest.raises(ConflictError) as exc:
        ensure_compatible("PH-01", "PH_METER", "DENSITY", required)
    assert exc.value.code == "INSTRUMENT_TYPE_MISMATCH"
    assert exc.value.details == {
        "instrument_type": "PH_METER",
        "required_instrument_type": required,
    }


@pytest.mark.parametrize("unit", ["ph", "PH", "pH ", "mV"])
def test_unit_must_match_exactly(unit: str) -> None:
    ensure_unit("pH", "pH")
    with pytest.raises(BusinessRuleError) as exc:
        ensure_unit(unit, "pH")
    assert exc.value.code == "UNIT_MISMATCH"
