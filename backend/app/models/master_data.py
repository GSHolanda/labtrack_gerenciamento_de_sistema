"""Cadastros: clientes, produtos, tipos de teste, plano analítico e instrumentos."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, IdMixin, TimestampMixin, enum_check
from app.domain.enums import InstrumentStatus, InstrumentType

SPEC_RANGE_CHECK = "spec_min IS NULL OR spec_max IS NULL OR spec_min <= spec_max"


class Client(IdMixin, TimestampMixin, Base):
    __tablename__ = "clients"

    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    tax_id: Mapped[str | None] = mapped_column(String(20), unique=True)
    contact_email: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")


class Product(IdMixin, TimestampMixin, Base):
    __tablename__ = "products"

    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    category: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")

    specifications: Mapped[list["ProductSpecification"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class TestDefinition(IdMixin, TimestampMixin, Base):
    """Tipo de teste com limites padrão de especificação (inclusivos)."""

    __test__ = False  # evita que o pytest tente coletar a classe
    __tablename__ = "test_definitions"
    __table_args__ = (
        CheckConstraint("spec_min IS NOT NULL OR spec_max IS NOT NULL", name="spec_has_limit"),
        CheckConstraint(SPEC_RANGE_CHECK, name="spec_range"),
        CheckConstraint("decimal_places BETWEEN 0 AND 6", name="decimal_places_range"),
        enum_check("instrument_type", InstrumentType),
    )

    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    unit: Mapped[str] = mapped_column(String(20))
    spec_min: Mapped[Decimal | None]
    spec_max: Mapped[Decimal | None]
    method: Mapped[str] = mapped_column(String(150))
    instrument_type: Mapped[str | None] = mapped_column(String(40))
    decimal_places: Mapped[int] = mapped_column(SmallInteger, default=2, server_default="2")
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")


class ProductSpecification(IdMixin, TimestampMixin, Base):
    """Plano analítico: testes do produto e limites que sobrescrevem o padrão."""

    __tablename__ = "product_specifications"
    __table_args__ = (
        UniqueConstraint("product_id", "test_definition_id"),
        CheckConstraint(SPEC_RANGE_CHECK, name="spec_range"),
    )

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    test_definition_id: Mapped[int] = mapped_column(
        ForeignKey("test_definitions.id", ondelete="RESTRICT"), index=True
    )
    spec_min: Mapped[Decimal | None]
    spec_max: Mapped[Decimal | None]

    product: Mapped[Product] = relationship(back_populates="specifications")
    test_definition: Mapped[TestDefinition] = relationship(lazy="joined")


class Instrument(IdMixin, TimestampMixin, Base):
    """Equipamento de laboratório integrado via API (autenticado por chave própria)."""

    __tablename__ = "instruments"
    __table_args__ = (
        enum_check("instrument_type", InstrumentType),
        enum_check("status", InstrumentStatus),
    )

    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    instrument_type: Mapped[str] = mapped_column(String(40), index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(80))
    serial_number: Mapped[str | None] = mapped_column(String(80), unique=True)
    location: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(
        String(20), default=InstrumentStatus.ACTIVE, server_default=InstrumentStatus.ACTIVE
    )
    calibration_due_date: Mapped[date | None]
    # SHA-256 da chave de integração; a chave em si nunca é armazenada.
    api_key_hash: Mapped[str] = mapped_column(String(255), unique=True)
    last_communication_at: Mapped[datetime | None]
