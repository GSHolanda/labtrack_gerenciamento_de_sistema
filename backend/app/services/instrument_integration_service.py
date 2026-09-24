"""Integração com instrumentos (RN-19 a RN-24): worklist, resultados e heartbeat.

Toda mensagem de resultado é registrada em ``instrument_results``. Uma mensagem
aceita grava o resultado, o log e a auditoria na mesma transação; uma recusada
não grava resultado algum, mas fica no log com o motivo e é auditada.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import utcnow, utctoday
from app.core.exceptions import (
    AppError,
    AuthenticationError,
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from app.core.security import INSTRUMENT_KEY_MAX_LENGTH, hash_instrument_key
from app.domain.audit import Actor, AuditAction
from app.domain.enums import (
    InstrumentMessageStatus,
    ResultSource,
    SampleStatus,
    SampleTestStatus,
)
from app.domain.instruments import ensure_can_measure, ensure_compatible, ensure_unit
from app.models import Instrument, InstrumentResult, Sample, SampleTest, TestResult
from app.repositories.instrument_repository import (
    InstrumentMessageRepository,
    InstrumentRepository,
)
from app.repositories.sample_repository import SampleRepository, SampleTestRepository
from app.schemas.instruments import InstrumentResultSubmission
from app.services.audit_service import AuditService
from app.services.result_service import ResultService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AcceptedResult:
    message: InstrumentResult
    result: TestResult


class InstrumentIntegrationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.instruments = InstrumentRepository(session)
        self.messages = InstrumentMessageRepository(session)
        self.samples = SampleRepository(session)
        self.sample_tests = SampleTestRepository(session)
        self.results = ResultService(session)
        self.audit = AuditService(session)

    def authenticate(self, api_key: str | None) -> Instrument:
        """RN-19: o equipamento é identificado pela própria chave (comparada pelo hash)."""
        instrument = None
        if api_key and len(api_key) <= INSTRUMENT_KEY_MAX_LENGTH:
            instrument = self.instruments.find_by_key_hash(hash_instrument_key(api_key))
        if instrument is None:
            logger.warning("Requisição de instrumento com chave ausente ou inválida.")
            raise AuthenticationError(
                "Chave de instrumento ausente ou inválida.", code="INVALID_INSTRUMENT_KEY"
            )
        return instrument

    def heartbeat(self, instrument: Instrument, instrument_code: str | None) -> Instrument:
        """Registra a comunicação, mesmo de um equipamento parado ou sem calibração."""
        if instrument_code is not None:
            _ensure_identity(instrument, instrument_code)
        self._touch(instrument)
        self.session.commit()
        return instrument

    def worklist(self, instrument: Instrument, limit: int) -> list[SampleTest]:
        self._touch(instrument)
        self.session.commit()
        ensure_can_measure(
            instrument.code, instrument.status, instrument.calibration_due_date, utctoday()
        )
        return self.sample_tests.pending_for_instrument_type(instrument.instrument_type, limit)

    def submit_result(self, instrument: Instrument, payload: Any) -> AcceptedResult:
        """Valida RN-19 a RN-23 e grava o resultado; recusas ficam no log (RN-24)."""
        fields = {
            "instrument_id": instrument.id,
            "payload": payload,
            "received_at": utcnow(),
            **_describe(payload),
        }
        try:
            data = _parse(payload)
            fields.update(
                sample_code=data.sample_code,
                test_code=data.test,
                value=data.result,
                unit=data.unit,
            )
            _ensure_identity(instrument, data.instrument_id)
            ensure_can_measure(
                instrument.code, instrument.status, instrument.calibration_due_date, utctoday()
            )
            sample = self._sample_in_analysis(data.sample_code)
            sample_test = self._pending_test(instrument, sample, data)
            result = self.results.record(
                sample_test,
                data.result,
                actor=_actor(instrument),
                source=ResultSource.INSTRUMENT,
                instrument_id=instrument.id,
            )
            self._touch(instrument)
            message = self.messages.add(
                InstrumentResult(
                    **fields, status=InstrumentMessageStatus.ACCEPTED, test_result_id=result.id
                )
            )
        except AppError as error:
            self._reject(instrument, fields, error)
            raise
        except IntegrityError as exc:
            # Dois resultados simultâneos para o mesmo teste: o índice único do banco
            # impede a sobrescrita e a segunda mensagem é recusada como duplicada.
            logger.warning("Resultado concorrente recusado: %s", exc.orig)
            error = ConflictError(
                "O teste recebeu outro resultado ao mesmo tempo; nada foi sobrescrito.",
                code="TEST_ALREADY_COMPLETED",
            )
            self._reject(instrument, fields, error)
            raise error from exc
        self.session.commit()
        return AcceptedResult(message, result)

    # --- Auxiliares -----------------------------------------------------------

    def _sample_in_analysis(self, sample_code: str) -> Sample:
        sample = self.samples.find_by_code_for_update(sample_code)
        if sample is None:
            raise NotFoundError(f"Amostra {sample_code} não encontrada.", code="SAMPLE_NOT_FOUND")
        if sample.status != SampleStatus.IN_ANALYSIS:  # RN-22
            raise ConflictError(
                f"A amostra {sample.sample_code} não está em análise (status: {sample.status}).",
                code="SAMPLE_NOT_IN_ANALYSIS",
                details={"status": sample.status},
            )
        return sample

    def _pending_test(
        self, instrument: Instrument, sample: Sample, data: InstrumentResultSubmission
    ) -> SampleTest:
        sample_test = self.sample_tests.find_in_sample(sample.id, data.test)
        if sample_test is None:
            raise ConflictError(
                f"O teste {data.test} não está atribuído à amostra {sample.sample_code}.",
                code="TEST_NOT_ASSIGNED",
            )
        if sample_test.status == SampleTestStatus.CANCELLED:
            raise ConflictError(
                f"O teste {data.test} da amostra {sample.sample_code} foi cancelado.",
                code="SAMPLE_TEST_CANCELLED",
            )
        ensure_compatible(  # RN-21
            instrument.code,
            instrument.instrument_type,
            data.test,
            sample_test.test_definition.instrument_type,
        )
        if sample_test.status != SampleTestStatus.PENDING:  # RN-22: nunca sobrescreve
            raise ConflictError(
                f"O teste {data.test} da amostra {sample.sample_code} já tem resultado. "
                "Correções são manuais e exigem justificativa.",
                code="TEST_ALREADY_COMPLETED",
            )
        ensure_unit(data.unit, sample_test.unit)  # RN-23
        return sample_test

    def _reject(self, instrument: Instrument, fields: dict[str, Any], error: AppError) -> None:
        """Descarta o que a mensagem alterou e grava só o log e a auditoria da recusa.

        Se a amostra existe, a recusa fica na timeline dela, qualquer que seja o motivo.
        """
        self.session.rollback()
        self._touch(instrument)
        sample_code = fields.get("sample_code")
        sample_id = self.samples.id_by_code(sample_code) if sample_code else None
        message = self.messages.add(
            InstrumentResult(
                **fields,
                status=InstrumentMessageStatus.REJECTED,
                error_code=error.code,
                error_message=error.message,
            )
        )
        self.audit.record(
            _actor(instrument),
            AuditAction.INSTRUMENT_MESSAGE_REJECTED,
            entity_type="instrument_message",
            entity_id=message.id,
            entity_label=(
                f"{instrument.code}: {fields.get('sample_code') or '?'} / "
                f"{fields.get('test_code') or '?'}"
            ),
            sample_id=sample_id,
            new_value={
                "error_code": error.code,
                "sample_code": fields.get("sample_code"),
                "test": fields.get("test_code"),
                "result": fields.get("value"),
                "unit": fields.get("unit"),
            },
            reason=error.message,
        )
        self.session.commit()
        error.details = {**(error.details or {}), "message_id": message.id}
        logger.info("Mensagem %s de %s recusada: %s", message.id, instrument.code, error.code)

    def _touch(self, instrument: Instrument) -> None:
        instrument.last_communication_at = utcnow()


def _actor(instrument: Instrument) -> Actor:
    return Actor.instrument(instrument.id, instrument.code)


def _ensure_identity(instrument: Instrument, instrument_code: str) -> None:
    """RN-19: o ``instrument_id`` informado precisa ser o dono da chave."""
    if instrument_code.upper() != instrument.code.upper():
        raise PermissionDeniedError(
            f"A chave pertence ao equipamento {instrument.code}, não a {instrument_code}.",
            code="INSTRUMENT_ID_MISMATCH",
            details={"key_owner": instrument.code, "received": instrument_code},
        )


def _parse(payload: Any) -> InstrumentResultSubmission:
    try:
        return InstrumentResultSubmission.model_validate(payload)
    except ValidationError as exc:
        errors = [
            {"field": ".".join(str(part) for part in err["loc"]), "message": err["msg"]}
            for err in exc.errors()
        ]
        raise BusinessRuleError(
            "Mensagem inválida: campos ausentes ou com formato incorreto.",
            code="INVALID_PAYLOAD",
            details={"errors": errors},
        ) from exc


def _describe(payload: Any) -> dict[str, str | Decimal | datetime | None]:
    """Identifica a mensagem para o log mesmo quando ela não passa na validação."""
    if not isinstance(payload, dict):
        return {}

    def text(key: str, size: int, *, upper: bool = False) -> str | None:
        value = payload.get(key)
        if not isinstance(value, str):
            return None
        value = value.strip()
        return (value.upper() if upper else value)[:size] or None

    return {
        "sample_code": text("sample_code", 20, upper=True),
        "test_code": text("test", 30, upper=True),
        "unit": text("unit", 20),
    }
