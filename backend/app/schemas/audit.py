"""Contratos de consulta do audit trail e da timeline da amostra."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.domain.enums import ActorType


@dataclass(frozen=True)
class AuditFilter:
    user_id: int | None = None
    instrument_id: int | None = None
    actor_type: str | None = None
    action: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    sample_id: int | None = None
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None


class AuditEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    occurred_at: datetime
    actor_type: ActorType
    actor_name: str
    user_id: int | None
    instrument_id: int | None
    action: str
    entity_type: str
    entity_id: str
    entity_label: str | None
    sample_id: int | None
    old_value: Any | None
    new_value: Any | None
    reason: str | None

    @field_validator("occurred_at")
    @classmethod
    def timestamp_in_utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class AuditRead(AuditEvent):
    request_id: str | None
    ip_address: str | None
    previous_hash: str | None
    record_hash: str


class AuditVerificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    valid: bool
    checked_records: int
    first_invalid_id: int | None
    error_code: str | None


class TimelineEvent(AuditEvent):
    is_correction: bool
    has_oos: bool


def to_timeline_event(entry: Any) -> TimelineEvent:
    return TimelineEvent(
        **AuditEvent.model_validate(entry).model_dump(),
        is_correction=entry.action == "RESULT_AMENDED",
        has_oos=any(
            isinstance(value, dict) and value.get("spec_status") == "OOS"
            for value in (entry.old_value, entry.new_value)
        ),
    )
