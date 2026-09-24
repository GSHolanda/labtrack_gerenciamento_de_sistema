"""Regras puras da integração com instrumentos (RN-20, RN-21 e RN-23)."""

from datetime import UTC, date, datetime, timedelta

from app.core.exceptions import BusinessRuleError, ConflictError
from app.domain.enums import InstrumentStatus, SamplePriority

# Sem comunicação (heartbeat, worklist ou resultado) por mais que isto: offline.
ONLINE_WINDOW = timedelta(minutes=5)

# Ordem da worklist: o equipamento mede primeiro as amostras mais urgentes.
PRIORITY_RANK: dict[SamplePriority, int] = {
    SamplePriority.URGENT: 0,
    SamplePriority.HIGH: 1,
    SamplePriority.NORMAL: 2,
    SamplePriority.LOW: 3,
}


def calibration_is_valid(due_date: date | None, today: date) -> bool:
    """A calibração vale até o dia do vencimento, inclusive. Sem data, não é válida."""
    return due_date is not None and today <= due_date


def is_online(last_communication_at: datetime | None, now: datetime) -> bool:
    if last_communication_at is None:
        return False
    if last_communication_at.tzinfo is None:  # SQLite não preserva o fuso
        last_communication_at = last_communication_at.replace(tzinfo=UTC)
    return now - last_communication_at <= ONLINE_WINDOW


def ensure_can_measure(
    code: str, status: str, calibration_due_date: date | None, today: date
) -> None:
    """RN-20: só um equipamento ativo e calibrado entrega resultados."""
    if status != InstrumentStatus.ACTIVE:
        raise ConflictError(
            f"O equipamento {code} não está ativo (status: {status}).",
            code="INSTRUMENT_NOT_ACTIVE",
            details={"status": status},
        )
    if not calibration_is_valid(calibration_due_date, today):
        message = (
            f"A calibração do equipamento {code} venceu em {calibration_due_date:%d/%m/%Y}."
            if calibration_due_date
            else f"O equipamento {code} não tem calibração registrada."
        )
        raise ConflictError(
            message,
            code="CALIBRATION_EXPIRED",
            details={"calibration_due_date": calibration_due_date},
        )


def ensure_compatible(
    instrument_code: str, instrument_type: str, test_code: str, required_type: str | None
) -> None:
    """RN-21: o tipo do equipamento precisa ser o exigido pelo teste."""
    if required_type != instrument_type:
        raise ConflictError(
            f"O equipamento {instrument_code} ({instrument_type}) não executa o teste {test_code}.",
            code="INSTRUMENT_TYPE_MISMATCH",
            details={"instrument_type": instrument_type, "required_instrument_type": required_type},
        )


def ensure_unit(received: str, expected: str) -> None:
    """RN-23: a unidade enviada deve ser exatamente a especificada (mS ≠ ms)."""
    if received != expected:
        raise BusinessRuleError(
            f"Unidade '{received}' diferente da especificada para o teste ('{expected}').",
            code="UNIT_MISMATCH",
            details={"expected": expected, "received": received},
        )
