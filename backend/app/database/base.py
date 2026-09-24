"""Base declarativa, convenção de nomes e tipos compartilhados pelos modelos."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Nomes previsíveis para constraints: migrações do Alembic ficam estáveis e as
# mensagens de erro do banco apontam exatamente qual regra foi violada.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# BIGINT no PostgreSQL; INTEGER no SQLite (necessário para autoincremento nos testes).
BigIntPK = BigInteger().with_variant(Integer, "sqlite")
# JSONB no PostgreSQL, JSON genérico nos demais bancos.
JsonDocument = JSON().with_variant(JSONB, "postgresql")
# Valores analíticos: decimal exato, nunca ponto flutuante.
AnalyticalValue = Numeric(14, 4, asdecimal=True)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {  # noqa: RUF012
        datetime: DateTime(timezone=True),
        Decimal: AnalyticalValue,
    }


class IdMixin:
    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


def enum_check(column: str, enum_cls: type[StrEnum], name: str | None = None) -> CheckConstraint:
    """Cria ``CHECK (column IN (...))`` a partir de um enum do domínio."""
    values = ", ".join(f"'{member.value}'" for member in enum_cls)
    return CheckConstraint(f"{column} IN ({values})", name=name or f"{column}_valid")
