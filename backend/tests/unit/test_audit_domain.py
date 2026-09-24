from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

from app.domain.audit import canonical_timestamp, compute_record_hash, to_audit_value

FIELDS = {"action": "RESULT_AMENDED", "old_value": {"value": "7.3"}, "new_value": {"value": "7.1"}}


def test_hash_is_deterministic() -> None:
    assert compute_record_hash(FIELDS, None) == compute_record_hash(dict(FIELDS), None)


def test_hash_changes_when_content_changes() -> None:
    tampered = {**FIELDS, "new_value": {"value": "7.2"}}
    assert compute_record_hash(FIELDS, None) != compute_record_hash(tampered, None)


def test_hash_depends_on_previous_record() -> None:
    assert compute_record_hash(FIELDS, "a" * 64) != compute_record_hash(FIELDS, "b" * 64)


def test_decimal_values_are_serialized_without_precision_loss() -> None:
    assert to_audit_value({"value": Decimal("7.2000")}) == {"value": "7.2"}
    assert to_audit_value(Decimal("0.1") + Decimal("0.2")) == "0.3"


def test_timestamps_are_canonical_across_timezones() -> None:
    utc = datetime(2026, 9, 23, 14, 32, tzinfo=UTC)
    sao_paulo = utc.astimezone(timezone(timedelta(hours=-3)))

    assert canonical_timestamp(utc) == canonical_timestamp(sao_paulo)
    assert canonical_timestamp(utc) == canonical_timestamp(utc.replace(tzinfo=None))
