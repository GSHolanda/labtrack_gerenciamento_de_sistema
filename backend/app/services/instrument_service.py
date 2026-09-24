"""Gestão de instrumentos: cadastro, alteração, rotação de chave e log de mensagens."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import generate_instrument_key, hash_instrument_key
from app.domain.audit import AuditAction
from app.domain.pagination import PageRequest, PageResult
from app.models import Instrument, InstrumentResult, User
from app.repositories.instrument_repository import (
    InstrumentMessageRepository,
    InstrumentRepository,
)
from app.schemas.instruments import (
    InstrumentCreate,
    InstrumentFilter,
    InstrumentMessageFilter,
    InstrumentUpdate,
)
from app.services.audit_service import AuditService, actor_of, diff, snapshot

# Estado auditável. O hash da chave nunca vai para o audit trail.
INSTRUMENT_FIELDS = (
    "code",
    "name",
    "instrument_type",
    "manufacturer",
    "model",
    "serial_number",
    "location",
    "status",
    "calibration_due_date",
)


@dataclass(frozen=True)
class IssuedKey:
    """Instrumento e a chave recém-gerada, que só existe em texto nesta resposta."""

    instrument: Instrument
    api_key: str


class InstrumentService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.instruments = InstrumentRepository(session)
        self.messages = InstrumentMessageRepository(session)
        self.audit = AuditService(session)

    def search(self, filters: InstrumentFilter, page: PageRequest) -> PageResult[Instrument]:
        return self.instruments.search(filters, page)

    def get(self, instrument_id: int) -> Instrument:
        instrument = self.instruments.get(instrument_id)
        if instrument is None:
            raise NotFoundError(
                f"Equipamento {instrument_id} não encontrado.", code="INSTRUMENT_NOT_FOUND"
            )
        return instrument

    def create(self, data: InstrumentCreate, actor: User) -> IssuedKey:
        if self.instruments.find_by_code(data.code):
            raise _duplicate("código", data.code)
        if data.serial_number and self.instruments.exists_with_serial(data.serial_number):
            raise _duplicate("número de série", data.serial_number)

        api_key = generate_instrument_key()
        instrument = self.instruments.add(
            Instrument(**data.model_dump(), api_key_hash=hash_instrument_key(api_key))
        )
        self.audit.record(
            actor_of(actor),
            AuditAction.INSTRUMENT_CREATED,
            entity_type="instrument",
            entity_id=instrument.id,
            entity_label=instrument.code,
            new_value=snapshot(instrument, INSTRUMENT_FIELDS),
        )
        self.session.commit()
        return IssuedKey(instrument, api_key)

    def update(self, instrument_id: int, data: InstrumentUpdate, actor: User) -> Instrument:
        instrument = self.get(instrument_id)
        changes = data.model_dump(exclude_unset=True)
        serial = changes.get("serial_number")
        if serial and self.instruments.exists_with_serial(serial, exclude_id=instrument.id):
            raise _duplicate("número de série", serial)

        before = snapshot(instrument, INSTRUMENT_FIELDS)
        for name, value in changes.items():
            setattr(instrument, name, value)
        old_value, new_value = diff(before, snapshot(instrument, INSTRUMENT_FIELDS))
        if new_value:
            self.session.flush()
            self.audit.record(
                actor_of(actor),
                AuditAction.INSTRUMENT_UPDATED,
                entity_type="instrument",
                entity_id=instrument.id,
                entity_label=instrument.code,
                old_value=old_value,
                new_value=new_value,
            )
        self.session.commit()
        return instrument

    def rotate_key(self, instrument_id: int, reason: str | None, actor: User) -> IssuedKey:
        """Gera nova chave: a anterior deixa de autenticar no mesmo commit."""
        instrument = self.get(instrument_id)
        api_key = generate_instrument_key()
        instrument.api_key_hash = hash_instrument_key(api_key)
        self.session.flush()
        self.audit.record(
            actor_of(actor),
            AuditAction.INSTRUMENT_KEY_ROTATED,
            entity_type="instrument",
            entity_id=instrument.id,
            entity_label=instrument.code,
            reason=reason,
        )
        self.session.commit()
        return IssuedKey(instrument, api_key)

    def search_messages(
        self, instrument_id: int, filters: InstrumentMessageFilter, page: PageRequest
    ) -> PageResult[InstrumentResult]:
        self.get(instrument_id)
        return self.messages.search(instrument_id, filters, page)


def _duplicate(field: str, value: str) -> ConflictError:
    return ConflictError(
        f"Já existe um equipamento com {field} '{value}'.", code="DUPLICATED_INSTRUMENT"
    )
