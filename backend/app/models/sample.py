"""Operação do laboratório: amostras, histórico de status, testes e resultados."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, IdMixin, TimestampMixin, enum_check
from app.domain.enums import (
    ResultSource,
    SampleOrigin,
    SamplePriority,
    SampleStatus,
    SampleTestStatus,
    SpecStatus,
)
from app.models.master_data import SPEC_RANGE_CHECK, Client, Instrument, Product, TestDefinition
from app.models.security import User


class Sample(IdMixin, TimestampMixin, Base):
    __tablename__ = "samples"
    __table_args__ = (
        enum_check("status", SampleStatus),
        enum_check("priority", SamplePriority),
        enum_check("origin", SampleOrigin),
        # Integridade no banco: não existe amostra finalizada sem revisor.
        CheckConstraint(
            "status NOT IN ('APPROVED', 'REJECTED') "
            "OR (reviewed_by_id IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="reviewed_when_final",
        ),
        Index("ix_samples_status_received_at", "status", "received_at"),
    )

    sample_code: Mapped[str] = mapped_column(String(20), unique=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"), index=True
    )
    lot_number: Mapped[str] = mapped_column(String(50), index=True)
    origin: Mapped[str] = mapped_column(String(30))
    received_at: Mapped[datetime] = mapped_column(index=True)
    priority: Mapped[str] = mapped_column(
        String(10), default=SamplePriority.NORMAL, server_default=SamplePriority.NORMAL
    )
    status: Mapped[str] = mapped_column(
        String(20), default=SampleStatus.RECEIVED, server_default=SampleStatus.RECEIVED
    )
    responsible_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    submitted_at: Mapped[datetime | None]
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reviewed_at: Mapped[datetime | None]
    review_comment: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None]
    # Optimistic locking: o SQLAlchemy inclui "WHERE version = ?" em cada UPDATE.
    version: Mapped[int] = mapped_column(default=1, server_default="1")

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012

    product: Mapped[Product] = relationship(lazy="joined")
    client: Mapped[Client] = relationship(lazy="joined")
    responsible: Mapped[User | None] = relationship(foreign_keys=[responsible_id])
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])
    reviewed_by: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_id])
    tests: Mapped[list["SampleTest"]] = relationship(
        back_populates="sample", order_by="SampleTest.id"
    )
    status_history: Mapped[list["SampleStatusHistory"]] = relationship(
        back_populates="sample", order_by="SampleStatusHistory.changed_at"
    )


class SampleStatusHistory(IdMixin, Base):
    """Histórico de transições de status (append-only)."""

    __tablename__ = "sample_status_history"
    __table_args__ = (
        enum_check("to_status", SampleStatus),
        CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('RECEIVED', 'IN_ANALYSIS', 'AWAITING_REVIEW', 'APPROVED', 'REJECTED', 'CANCELLED')",
            name="from_status_valid",
        ),
        Index("ix_sample_status_history_sample_changed", "sample_id", "changed_at"),
    )

    sample_id: Mapped[int] = mapped_column(ForeignKey("samples.id", ondelete="RESTRICT"))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    changed_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    changed_at: Mapped[datetime] = mapped_column(server_default=func.now())
    reason: Mapped[str | None] = mapped_column(Text)

    sample: Mapped[Sample] = relationship(back_populates="status_history")
    changed_by: Mapped[User] = relationship()


class SampleTest(IdMixin, TimestampMixin, Base):
    """Teste atribuído à amostra, com snapshot da especificação vigente (RN-06)."""

    __tablename__ = "sample_tests"
    __table_args__ = (
        UniqueConstraint("sample_id", "test_definition_id"),
        enum_check("status", SampleTestStatus),
        CheckConstraint(SPEC_RANGE_CHECK, name="spec_range"),
    )

    sample_id: Mapped[int] = mapped_column(
        ForeignKey("samples.id", ondelete="RESTRICT"), index=True
    )
    test_definition_id: Mapped[int] = mapped_column(
        ForeignKey("test_definitions.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default=SampleTestStatus.PENDING, server_default=SampleTestStatus.PENDING
    )
    spec_min: Mapped[Decimal | None]
    spec_max: Mapped[Decimal | None]
    unit: Mapped[str] = mapped_column(String(20))
    assigned_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assigned_at: Mapped[datetime] = mapped_column(server_default=func.now())

    sample: Mapped[Sample] = relationship(back_populates="tests")
    test_definition: Mapped[TestDefinition] = relationship(lazy="joined")
    results: Mapped[list["TestResult"]] = relationship(
        back_populates="sample_test", order_by="TestResult.version"
    )


class TestResult(IdMixin, Base):
    """Resultado analítico. Correções criam nova versão; nada é sobrescrito (RN-17)."""

    __test__ = False
    __tablename__ = "test_results"
    __table_args__ = (
        UniqueConstraint("sample_test_id", "version"),
        enum_check("spec_status", SpecStatus),
        enum_check("source", ResultSource),
        # Todo resultado é atribuível a um usuário ou a um equipamento.
        CheckConstraint(
            "(source = 'MANUAL' AND entered_by_id IS NOT NULL) "
            "OR (source = 'INSTRUMENT' AND instrument_id IS NOT NULL)",
            name="attributable",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("version = 1 OR change_reason IS NOT NULL", name="amend_has_reason"),
        # Apenas uma versão vigente por teste.
        Index(
            "uq_test_results_current_per_test",
            "sample_test_id",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current"),
        ),
    )

    sample_test_id: Mapped[int] = mapped_column(ForeignKey("sample_tests.id", ondelete="RESTRICT"))
    value: Mapped[Decimal]
    unit: Mapped[str] = mapped_column(String(20))
    spec_status: Mapped[str] = mapped_column(String(10), index=True)
    source: Mapped[str] = mapped_column(String(12))
    entered_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    instrument_id: Mapped[int | None] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"), index=True
    )
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    is_current: Mapped[bool] = mapped_column(default=True, server_default="true")
    change_reason: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    entered_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)

    sample_test: Mapped[SampleTest] = relationship(back_populates="results")
    entered_by: Mapped[User | None] = relationship()
    instrument: Mapped[Instrument | None] = relationship()
