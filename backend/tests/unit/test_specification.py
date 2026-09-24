from decimal import Decimal

import pytest

from app.domain.enums import SpecStatus
from app.domain.sample_code import format_sample_code, parse_sequence
from app.domain.specification import SpecLimits, evaluate, resolve_limits, validate_limits

DEFAULT = SpecLimits(Decimal("6.5"), Decimal("7.5"))


@pytest.mark.rules("RN-06")
def test_default_limits_apply_without_override() -> None:
    assert resolve_limits(DEFAULT) == DEFAULT


@pytest.mark.rules("RN-06")
def test_product_override_replaces_both_limits() -> None:
    assert resolve_limits(DEFAULT, SpecLimits(Decimal("5.0"), Decimal("6.0"))) == SpecLimits(
        Decimal("5.0"), Decimal("6.0")
    )


@pytest.mark.rules("RN-06")
def test_product_can_override_a_single_side() -> None:
    assert resolve_limits(DEFAULT, SpecLimits(None, Decimal("7.0"))) == SpecLimits(
        Decimal("6.5"), Decimal("7.0")
    )


def test_limit_validation() -> None:
    assert validate_limits(Decimal("1"), Decimal("2")) is None
    assert validate_limits(None, Decimal("0.5")) is None
    assert validate_limits(Decimal("2"), Decimal("1")) is not None


@pytest.mark.rules("RN-01")
def test_sample_code_format_and_parse() -> None:
    assert format_sample_code(2026, 7) == "SMP-2026-0007"
    assert format_sample_code(2026, 12345) == "SMP-2026-12345"
    assert parse_sequence("SMP-2026-0007") == 7
    assert parse_sequence("XYZ-2026-0007") is None


# --- Avaliação OOS (RN-16) ----------------------------------------------------


@pytest.mark.rules("RN-16")
@pytest.mark.parametrize(
    ("value", "spec_min", "spec_max", "expected"),
    [
        ("7.2", "6.5", "7.5", SpecStatus.IN_SPEC),  # exemplo do enunciado
        ("8.1", "6.5", "7.5", SpecStatus.OOS),
        ("7.5", "6.5", "7.5", SpecStatus.IN_SPEC),  # limite superior é inclusivo
        ("6.5", "6.5", "7.5", SpecStatus.IN_SPEC),  # limite inferior é inclusivo
        ("6.4999", "6.5", "7.5", SpecStatus.OOS),
        ("7.5001", "6.5", "7.5", SpecStatus.OOS),
        ("0.3", None, "0.5", SpecStatus.IN_SPEC),  # especificação unilateral
        ("0.7", None, "0.5", SpecStatus.OOS),
        ("99", "95", None, SpecStatus.IN_SPEC),
        ("94.9", "95", None, SpecStatus.OOS),
    ],
)
def test_evaluate(
    value: str, spec_min: str | None, spec_max: str | None, expected: SpecStatus
) -> None:
    def dec(raw: str | None) -> Decimal | None:
        return Decimal(raw) if raw is not None else None

    assert evaluate(Decimal(value), dec(spec_min), dec(spec_max)) == expected


@pytest.mark.rules("RN-16")
def test_evaluate_is_exact_where_float_would_fail() -> None:
    # Em float, 0.1 + 0.2 = 0.30000000000000004 > 0.3 e o resultado seria OOS.
    assert evaluate(Decimal("0.1") + Decimal("0.2"), None, Decimal("0.3")) == SpecStatus.IN_SPEC
