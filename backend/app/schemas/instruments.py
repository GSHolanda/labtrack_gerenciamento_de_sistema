"""Contratos dos instrumentos: gestão (usuários) e integração (equipamentos)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.core.clock import utcnow
from app.domain.enums import (
    InstrumentMessageStatus,
    InstrumentStatus,
    InstrumentType,
    SamplePriority,
    SpecStatus,
)
from app.domain.instruments import calibration_is_valid, is_online


def _upper(value: Any) -> Any:
    return value.strip().upper() if isinstance(value, str) else value


InstrumentCode = Annotated[
    str, BeforeValidator(_upper), StringConstraints(pattern=r"^[A-Z0-9_-]{2,40}$")
]
TestCode = Annotated[str, BeforeValidator(_upper), StringConstraints(pattern=r"^[A-Z0-9_-]{2,30}$")]
SampleCode = Annotated[str, BeforeValidator(_upper), StringConstraints(min_length=1, max_length=20)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Unit = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=1000)]


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True)
class InstrumentFilter:
    q: str | None = None
    status: str | None = None
    instrument_type: str | None = None


@dataclass(frozen=True)
class InstrumentMessageFilter:
    status: str | None = None


# --- Gestão -------------------------------------------------------------------


class InstrumentCreate(_Input):
    code: InstrumentCode = Field(
        examples=["PH-METER-01"], description="Identificador enviado pelo equipamento"
    )
    name: Name = Field(examples=["pHmetro de bancada"])
    instrument_type: InstrumentType
    manufacturer: ShortText | None = None
    model: ShortText | None = None
    serial_number: ShortText | None = None
    location: ShortText | None = Field(default=None, examples=["Sala 2 — Físico-química"])
    status: InstrumentStatus = InstrumentStatus.ACTIVE
    calibration_due_date: date = Field(
        description="Vencimento da calibração (válida até este dia, inclusive)"
    )


class InstrumentUpdate(_Input):
    """Código e tipo não mudam: identificam o equipamento nos resultados já gravados."""

    name: Name | None = None
    manufacturer: ShortText | None = None
    model: ShortText | None = None
    serial_number: ShortText | None = None
    location: ShortText | None = None
    status: InstrumentStatus | None = None
    calibration_due_date: date | None = None

    @model_validator(mode="after")
    def _required_fields_not_null(self) -> Self:
        cleared = [
            name
            for name in ("name", "status", "calibration_due_date")
            if name in self.model_fields_set and getattr(self, name) is None
        ]
        if cleared:
            raise ValueError(f"Campos obrigatórios não podem ser nulos: {', '.join(cleared)}.")
        return self


class KeyRotationRequest(_Input):
    reason: Reason | None = Field(default=None, examples=["Chave exposta em log do equipamento"])


class InstrumentRead(BaseModel):
    id: int
    code: str
    name: str
    instrument_type: InstrumentType
    manufacturer: str | None
    model: str | None
    serial_number: str | None
    location: str | None
    status: InstrumentStatus
    calibration_due_date: date | None
    calibration_valid: bool = Field(description="Calibração dentro do prazo hoje (UTC)")
    last_communication_at: datetime | None
    online: bool = Field(description="Comunicou-se com a API nos últimos 5 minutos")
    created_at: datetime


class InstrumentKeyRead(InstrumentRead):
    api_key: str = Field(
        description="Chave de integração. Exibida somente nesta resposta: guarde-a com segurança."
    )


class InstrumentMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    received_at: datetime
    status: InstrumentMessageStatus
    sample_code: str | None
    test_code: str | None
    value: Decimal | None
    unit: str | None
    error_code: str | None
    error_message: str | None
    test_result_id: int | None
    payload: Any = Field(description="Mensagem recebida, exatamente como enviada")

    _received_at_utc = field_validator("received_at")(_utc)


def to_instrument(instrument: Any) -> InstrumentRead:
    return InstrumentRead(**_instrument_fields(instrument))


def to_instrument_with_key(instrument: Any, api_key: str) -> InstrumentKeyRead:
    return InstrumentKeyRead(**_instrument_fields(instrument), api_key=api_key)


def _instrument_fields(instrument: Any) -> dict[str, Any]:
    now = utcnow()
    return {
        "id": instrument.id,
        "code": instrument.code,
        "name": instrument.name,
        "instrument_type": instrument.instrument_type,
        "manufacturer": instrument.manufacturer,
        "model": instrument.model,
        "serial_number": instrument.serial_number,
        "location": instrument.location,
        "status": instrument.status,
        "calibration_due_date": instrument.calibration_due_date,
        "calibration_valid": calibration_is_valid(instrument.calibration_due_date, now.date()),
        "last_communication_at": _utc(instrument.last_communication_at),
        "online": is_online(instrument.last_communication_at, now),
        "created_at": instrument.created_at,
    }


# --- Integração (X-Instrument-Key) ---------------------------------------------


class InstrumentResultSubmission(_Input):
    instrument_id: InstrumentCode = Field(
        examples=["PH-METER-01"], description="Código do equipamento; deve ser o dono da chave"
    )
    sample_code: SampleCode = Field(examples=["SMP-2026-0001"])
    test: TestCode = Field(examples=["PH"], description="Código do tipo de teste")
    result: Annotated[Decimal, Field(max_digits=14, decimal_places=4, examples=[7.21])]
    unit: Unit = Field(examples=["pH"])


class InstrumentResultAccepted(BaseModel):
    message_id: int
    status: InstrumentMessageStatus
    result_id: int
    sample_code: str
    test: str
    result: Decimal
    unit: str
    spec_status: SpecStatus
    spec_min: Decimal | None
    spec_max: Decimal | None


class WorklistItem(BaseModel):
    sample_code: str
    priority: SamplePriority
    received_at: datetime
    test: str
    test_name: str
    unit: str
    spec_min: Decimal | None
    spec_max: Decimal | None
    decimal_places: int
    assigned_at: datetime


class Worklist(BaseModel):
    instrument_id: str
    instrument_type: InstrumentType
    items: list[WorklistItem]


class HeartbeatRequest(_Input):
    instrument_id: InstrumentCode | None = Field(
        default=None, description="Opcional; se enviado, deve ser o dono da chave"
    )


class HeartbeatRead(BaseModel):
    instrument_id: str
    status: InstrumentStatus
    calibration_due_date: date | None
    calibration_valid: bool
    can_measure: bool = Field(description="Ativo e calibrado: pode enviar resultados")
    server_time: datetime


def to_accepted(message: Any, result: Any) -> InstrumentResultAccepted:
    sample_test = result.sample_test
    return InstrumentResultAccepted(
        message_id=message.id,
        status=message.status,
        result_id=result.id,
        sample_code=sample_test.sample.sample_code,
        test=sample_test.test_definition.code,
        result=result.value,
        unit=result.unit,
        spec_status=result.spec_status,
        spec_min=sample_test.spec_min,
        spec_max=sample_test.spec_max,
    )


def to_worklist(instrument: Any, sample_tests: list[Any]) -> Worklist:
    return Worklist(
        instrument_id=instrument.code,
        instrument_type=instrument.instrument_type,
        items=[
            WorklistItem(
                sample_code=test.sample.sample_code,
                priority=test.sample.priority,
                received_at=_utc(test.sample.received_at),
                test=test.test_definition.code,
                test_name=test.test_definition.name,
                unit=test.unit,
                spec_min=test.spec_min,
                spec_max=test.spec_max,
                decimal_places=test.test_definition.decimal_places,
                assigned_at=_utc(test.assigned_at),
            )
            for test in sample_tests
        ],
    )


def to_heartbeat(instrument: Any) -> HeartbeatRead:
    now = utcnow()
    calibrated = calibration_is_valid(instrument.calibration_due_date, now.date())
    return HeartbeatRead(
        instrument_id=instrument.code,
        status=instrument.status,
        calibration_due_date=instrument.calibration_due_date,
        calibration_valid=calibrated,
        can_measure=calibrated and instrument.status == InstrumentStatus.ACTIVE,
        server_time=now,
    )
