from sqlalchemy import func, or_, select

from app.domain.pagination import PageRequest, PageResult
from app.models import Instrument, InstrumentResult
from app.repositories.base import BaseRepository
from app.schemas.instruments import InstrumentFilter, InstrumentMessageFilter


class InstrumentRepository(BaseRepository[Instrument]):
    model = Instrument
    sortable = {  # noqa: RUF012
        "code": Instrument.code,
        "name": Instrument.name,
        "status": Instrument.status,
        "calibration_due_date": Instrument.calibration_due_date,
        "last_communication_at": Instrument.last_communication_at,
    }
    default_sort = (Instrument.code,)

    def find_by_code(self, code: str) -> Instrument | None:
        return self.session.scalar(
            select(Instrument).where(func.upper(Instrument.code) == code.upper())
        )

    def find_by_key_hash(self, key_hash: str) -> Instrument | None:
        return self.session.scalar(select(Instrument).where(Instrument.api_key_hash == key_hash))

    def exists_with_serial(self, serial_number: str, *, exclude_id: int | None = None) -> bool:
        statement = select(Instrument.id).where(Instrument.serial_number == serial_number)
        if exclude_id is not None:
            statement = statement.where(Instrument.id != exclude_id)
        return self.session.scalar(statement) is not None

    def search(self, filters: InstrumentFilter, page: PageRequest) -> PageResult[Instrument]:
        statement = select(Instrument)
        if filters.status:
            statement = statement.where(Instrument.status == filters.status)
        if filters.instrument_type:
            statement = statement.where(Instrument.instrument_type == filters.instrument_type)
        if filters.q:
            pattern = f"%{filters.q.lower()}%"
            statement = statement.where(
                or_(
                    func.lower(Instrument.code).like(pattern),
                    func.lower(Instrument.name).like(pattern),
                    func.lower(Instrument.location).like(pattern),
                    func.lower(Instrument.serial_number).like(pattern),
                )
            )
        return self.paginate(statement, page)


class InstrumentMessageRepository(BaseRepository[InstrumentResult]):
    """Log de mensagens: somente inclusão e leitura."""

    model = InstrumentResult
    sortable = {  # noqa: RUF012
        "received_at": InstrumentResult.received_at,
        "id": InstrumentResult.id,
    }
    default_sort = (InstrumentResult.received_at.desc(), InstrumentResult.id.desc())

    def search(
        self, instrument_id: int, filters: InstrumentMessageFilter, page: PageRequest
    ) -> PageResult[InstrumentResult]:
        statement = select(InstrumentResult).where(InstrumentResult.instrument_id == instrument_id)
        if filters.status:
            statement = statement.where(InstrumentResult.status == filters.status)
        return self.paginate(statement, page)
