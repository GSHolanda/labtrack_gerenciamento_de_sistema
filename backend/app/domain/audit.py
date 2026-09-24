"""Regras puras do audit trail: ações, ator e cálculo do hash encadeado."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.domain.enums import ActorType


class AuditAction(StrEnum):
    LOGIN_SUCCEEDED = "LOGIN_SUCCEEDED"
    LOGIN_FAILED = "LOGIN_FAILED"
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    CLIENT_CREATED = "CLIENT_CREATED"
    CLIENT_UPDATED = "CLIENT_UPDATED"
    PRODUCT_CREATED = "PRODUCT_CREATED"
    PRODUCT_UPDATED = "PRODUCT_UPDATED"
    SPECIFICATION_UPDATED = "SPECIFICATION_UPDATED"
    TEST_DEFINITION_CREATED = "TEST_DEFINITION_CREATED"
    TEST_DEFINITION_UPDATED = "TEST_DEFINITION_UPDATED"
    INSTRUMENT_CREATED = "INSTRUMENT_CREATED"
    INSTRUMENT_UPDATED = "INSTRUMENT_UPDATED"
    INSTRUMENT_KEY_ROTATED = "INSTRUMENT_KEY_ROTATED"
    SAMPLE_CREATED = "SAMPLE_CREATED"
    SAMPLE_UPDATED = "SAMPLE_UPDATED"
    SAMPLE_STATUS_CHANGED = "SAMPLE_STATUS_CHANGED"
    TESTS_ASSIGNED = "TESTS_ASSIGNED"
    TEST_CANCELLED = "TEST_CANCELLED"
    RESULT_ENTERED = "RESULT_ENTERED"
    RESULT_AMENDED = "RESULT_AMENDED"
    INSTRUMENT_MESSAGE_REJECTED = "INSTRUMENT_MESSAGE_REJECTED"
    REPORT_GENERATED = "REPORT_GENERATED"


@dataclass(frozen=True)
class Actor:
    """Quem executou a ação: um usuário, um instrumento ou o próprio sistema."""

    type: ActorType
    name: str
    user_id: int | None = None
    instrument_id: int | None = None

    @classmethod
    def user(cls, user_id: int, name: str) -> "Actor":
        return cls(ActorType.USER, name, user_id=user_id)

    @classmethod
    def instrument(cls, instrument_id: int, code: str) -> "Actor":
        return cls(ActorType.INSTRUMENT, code, instrument_id=instrument_id)

    @classmethod
    def system(cls, name: str = "LabTrack") -> "Actor":
        return cls(ActorType.SYSTEM, name)


def to_audit_value(value: Any) -> Any:
    """Converte valores para JSON estável (Decimal e datas viram texto, sem perda)."""
    if isinstance(value, dict):
        return {str(key): to_audit_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [to_audit_value(item) for item in value]
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, datetime):
        return canonical_timestamp(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    return value


def canonical_timestamp(moment: datetime) -> str:
    """UTC, precisão de microssegundos, sem fuso: igual em qualquer banco."""
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC).replace(tzinfo=None)
    return moment.isoformat(timespec="microseconds")


def compute_record_hash(fields: dict[str, Any], previous_hash: str | None) -> str:
    """SHA-256 do conteúdo do registro + hash do registro anterior (cadeia)."""
    canonical = json.dumps(
        {"previous_hash": previous_hash, **to_audit_value(fields)},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
