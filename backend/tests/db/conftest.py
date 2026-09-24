"""Fixtures de banco.

Por padrão os testes rodam em SQLite em memória (rápidos, sem infraestrutura).
Os testes marcados com ``postgres`` rodam contra um PostgreSQL real quando
``LABTRACK_TEST_DATABASE_URL`` está definida; caso contrário são pulados.
"""

import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database.base import Base
from app.database.session import build_engine, build_session_factory
from app.domain.enums import RoleCode, SampleOrigin
from app.models import (
    Client,
    Instrument,
    Product,
    Role,
    Sample,
    SampleTest,
    TestDefinition,
    User,
)

POSTGRES_URL = os.getenv("LABTRACK_TEST_DATABASE_URL")


@pytest.fixture
def engine() -> Iterator[Engine]:
    engine = build_engine("sqlite+pysqlite:///:memory:")
    engine.pool = StaticPool(engine.pool._creator)  # mesma conexão = mesmo banco em memória
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with build_session_factory(engine)() as session:
        yield session


@pytest.fixture
def postgres_engine() -> Iterator[Engine]:
    if not POSTGRES_URL:
        pytest.skip("LABTRACK_TEST_DATABASE_URL não definida")
    from alembic import command
    from alembic.config import Config

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", POSTGRES_URL)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = build_engine(POSTGRES_URL)
    yield engine
    engine.dispose()


@dataclass
class LabData:
    analyst: User
    instrument: Instrument
    sample: Sample
    sample_test: SampleTest


@pytest.fixture
def lab(session: Session) -> LabData:
    return create_lab_data(session)


def create_lab_data(session: Session) -> LabData:
    """Cria o mínimo de cadastros para uma amostra com um teste atribuído."""
    role = Role(code=RoleCode.ANALYST, name="Analista de Laboratório")
    analyst = User(
        username="carlos.silva",
        email="carlos@labtrack.dev",
        full_name="Carlos Silva",
        password_hash="x",
        role=role,
    )
    client = Client(code="CLI-001", name="Farmacêutica Aurora")
    product = Product(code="PRD-001", name="Xampu Neutro")
    ph = TestDefinition(
        code="PH",
        name="pH",
        unit="pH",
        spec_min=Decimal("6.5"),
        spec_max=Decimal("7.5"),
        method="Potenciometria",
        instrument_type="PH_METER",
    )
    instrument = Instrument(
        code="PH-METER-01", name="pHmetro de bancada", instrument_type="PH_METER", api_key_hash="x"
    )
    session.add_all([analyst, client, product, ph, instrument])
    session.flush()

    sample = Sample(
        sample_code="SMP-2026-0001",
        product_id=product.id,
        client_id=client.id,
        lot_number="L2026-001",
        origin=SampleOrigin.PRODUCTION,
        received_at=datetime.now(UTC),
        created_by_id=analyst.id,
    )
    session.add(sample)
    session.flush()
    sample_test = SampleTest(
        sample_id=sample.id,
        test_definition_id=ph.id,
        spec_min=ph.spec_min,
        spec_max=ph.spec_max,
        unit=ph.unit,
        assigned_by_id=analyst.id,
    )
    session.add(sample_test)
    session.commit()
    return LabData(analyst=analyst, instrument=instrument, sample=sample, sample_test=sample_test)
