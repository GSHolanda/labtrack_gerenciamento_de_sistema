from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.domain.audit import (
    HASHED_FIELDS,
    ChainEntry,
    canonical_timestamp,
    compute_record_hash,
    to_audit_value,
    verify_chain,
)

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


def _chain() -> list[ChainEntry]:
    fields = dict.fromkeys(HASHED_FIELDS)
    fields.update(FIELDS)
    entries = []
    previous_hash = None
    for record_id in (1, 3, 4):
        record_hash = compute_record_hash(fields, previous_hash)
        entries.append(ChainEntry(record_id, fields.copy(), previous_hash, record_hash))
        previous_hash = record_hash
    return entries


def test_empty_chain_is_valid() -> None:
    result = verify_chain([])
    assert result.valid
    assert result.checked_records == 0
    assert result.first_invalid_id is None
    assert result.error_code is None


def test_chain_accepts_sequence_gaps_from_rolled_back_transactions() -> None:
    result = verify_chain(_chain())
    assert result.valid
    assert result.checked_records == 3


@pytest.mark.parametrize("field", HASHED_FIELDS)
def test_verification_checks_every_hashed_field(field: str) -> None:
    entries = _chain()
    entries[1] = replace(entries[1], fields={**entries[1].fields, field: "adulterado"})
    result = verify_chain(entries)
    assert not result.valid
    assert result.checked_records == 2
    assert result.first_invalid_id == 3
    assert result.error_code == "RECORD_HASH_MISMATCH"


@pytest.mark.parametrize("removed_index", [0, 1])
def test_chain_detects_missing_first_or_middle_record(removed_index: int) -> None:
    entries = _chain()
    del entries[removed_index]
    result = verify_chain(entries)
    assert not result.valid
    assert result.first_invalid_id == entries[removed_index].id
    assert result.error_code == "PREVIOUS_HASH_MISMATCH"


def test_chain_stops_at_first_error() -> None:
    def entries():  # type: ignore[no-untyped-def]
        yield replace(_chain()[0], record_hash="0" * 64)
        raise AssertionError("Não deve ler registros após a primeira falha")

    result = verify_chain(entries())
    assert result.first_invalid_id == 1
    assert result.checked_records == 1


def test_chain_does_not_claim_to_detect_tail_removal_without_external_anchor() -> None:
    assert verify_chain(_chain()[:-1]).valid
