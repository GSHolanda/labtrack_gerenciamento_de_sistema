from decimal import Decimal

from app.domain.sample_code import format_sample_code, parse_sequence
from app.domain.specification import SpecLimits, resolve_limits, validate_limits

DEFAULT = SpecLimits(Decimal("6.5"), Decimal("7.5"))


def test_default_limits_apply_without_override() -> None:
    assert resolve_limits(DEFAULT) == DEFAULT


def test_product_override_replaces_both_limits() -> None:
    assert resolve_limits(DEFAULT, SpecLimits(Decimal("5.0"), Decimal("6.0"))) == SpecLimits(
        Decimal("5.0"), Decimal("6.0")
    )


def test_product_can_override_a_single_side() -> None:
    assert resolve_limits(DEFAULT, SpecLimits(None, Decimal("7.0"))) == SpecLimits(
        Decimal("6.5"), Decimal("7.0")
    )


def test_limit_validation() -> None:
    assert validate_limits(Decimal("1"), Decimal("2")) is None
    assert validate_limits(None, Decimal("0.5")) is None
    assert validate_limits(Decimal("2"), Decimal("1")) is not None


def test_sample_code_format_and_parse() -> None:
    assert format_sample_code(2026, 7) == "SMP-2026-0007"
    assert format_sample_code(2026, 12345) == "SMP-2026-12345"
    assert parse_sequence("SMP-2026-0007") == 7
    assert parse_sequence("XYZ-2026-0007") is None
