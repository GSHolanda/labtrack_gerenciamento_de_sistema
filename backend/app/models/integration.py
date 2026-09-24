from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, IdMixin, JsonDocument, enum_check
from app.domain.enums import InstrumentMessageStatus
from app.models.master_data import Instrument
from app.models.sample import TestResult


class InstrumentResult(IdMixin, Base):
    """Log de integração: toda mensagem recebida de um instrumento, aceita ou não (RN-24)."""

    __tablename__ = "instrument_results"
    __table_args__ = (
        enum_check("status", InstrumentMessageStatus),
        Index("ix_instrument_results_instrument_received", "instrument_id", "received_at"),
    )

    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="RESTRICT"))
    payload: Mapped[dict[str, Any]] = mapped_column(JsonDocument)
    sample_code: Mapped[str | None] = mapped_column(String(20))
    test_code: Mapped[str | None] = mapped_column(String(30))
    value: Mapped[Decimal | None]
    unit: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(10), index=True)
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(Text)
    test_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_results.id", ondelete="RESTRICT"), unique=True
    )
    received_at: Mapped[datetime] = mapped_column(server_default=func.now())

    instrument: Mapped[Instrument] = relationship()
    test_result: Mapped[TestResult | None] = relationship()
