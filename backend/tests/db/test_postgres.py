"""Testes que dependem de recursos do PostgreSQL (triggers, migrações, concorrência)."""

import threading
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import DBAPIError

from app.core.exceptions import AppError
from app.database.session import build_session_factory
from app.domain.enums import SampleStatus
from app.models import AuditLog, Instrument, InstrumentResult, TestResult, User
from app.schemas.samples import SampleCreate
from app.services.audit_service import AuditService
from app.services.instrument_integration_service import InstrumentIntegrationService
from app.services.sample_service import SampleService

from .conftest import create_lab_data

pytestmark = pytest.mark.postgres


def _insert_audit(engine: Engine) -> int:
    with build_session_factory(engine)() as session:
        lab = create_lab_data(session)
        log = AuditLog(
            actor_type="USER",
            user_id=lab.analyst.id,
            actor_name="Carlos Silva",
            action="RESULT_AMENDED",
            entity_type="test_result",
            entity_id="1",
            sample_id=lab.sample.id,
            old_value={"value": "7.3"},
            new_value={"value": "7.1"},
            reason="Erro de digitação",
            record_hash="a" * 64,
        )
        session.add(log)
        session.commit()
        return log.id


@pytest.mark.rules("RN-15")
@pytest.mark.parametrize(
    "statement",
    [
        'UPDATE audit_logs SET new_value = \'{"value": "9.9"}\' WHERE id = :id',
        "DELETE FROM audit_logs WHERE id = :id",
        "TRUNCATE audit_logs CASCADE",
    ],
    ids=["update", "delete", "truncate"],
)
def test_audit_logs_are_append_only(postgres_engine: Engine, statement: str) -> None:
    log_id = _insert_audit(postgres_engine)

    with postgres_engine.connect() as connection, pytest.raises(DBAPIError, match="append-only"):
        connection.execute(text(statement), {"id": log_id})

    with postgres_engine.connect() as connection:
        value = connection.execute(
            text("SELECT new_value ->> 'value' FROM audit_logs WHERE id = :id"), {"id": log_id}
        ).scalar_one()
    assert value == "7.1"


def test_migrations_match_models(postgres_engine: Engine) -> None:
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    import app.models  # noqa: F401
    from app.database.base import Base

    with postgres_engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []


@pytest.mark.rules("RN-22")
def test_concurrent_instrument_results_never_overwrite(postgres_engine: Engine) -> None:
    factory = build_session_factory(postgres_engine)
    with factory() as session:
        lab = create_lab_data(session)
        lab.sample.status = SampleStatus.IN_ANALYSIS
        lab.instrument.calibration_due_date = date.today() + timedelta(days=30)
        session.commit()
        instrument_id, sample_code = lab.instrument.id, lab.sample.sample_code

    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def send(value: str) -> None:
        with factory() as session:
            instrument = session.get(Instrument, instrument_id)
            service = InstrumentIntegrationService(session)
            payload = {
                "instrument_id": "PH-METER-01",
                "sample_code": sample_code,
                "test": "PH",
                "result": value,
                "unit": "pH",
            }
            barrier.wait()
            try:
                service.submit_result(instrument, payload)
                outcomes.append("ACCEPTED")
            except AppError as error:
                outcomes.append(error.code)

    threads = [threading.Thread(target=send, args=(value,)) for value in ("7.1", "7.2")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(outcomes) == ["ACCEPTED", "TEST_ALREADY_COMPLETED"]
    with factory() as session:
        [result] = session.scalars(select(TestResult)).all()
        assert result.is_current and result.version == 1
        statuses = sorted(session.scalars(select(InstrumentResult.status)).all())
        assert statuses == ["ACCEPTED", "REJECTED"]
        assert AuditService(session).verify().valid is True


@pytest.mark.rules("RN-01")
def test_concurrent_registrations_get_distinct_sequential_codes(postgres_engine: Engine) -> None:
    """O advisory lock serializa a numeração: sem código repetido nem lacuna."""
    factory = build_session_factory(postgres_engine)
    with factory() as session:
        lab = create_lab_data(session)
        analyst_id, product_id, client_id = (
            lab.analyst.id,
            lab.sample.product_id,
            lab.sample.client_id,
        )

    registrations = 6
    received_at = datetime.now(UTC) - timedelta(hours=1)
    barrier = threading.Barrier(registrations)
    codes: list[str] = []
    errors: list[str] = []

    def register() -> None:
        with factory() as session:
            actor = session.get(User, analyst_id)
            data = SampleCreate(
                product_id=product_id,
                client_id=client_id,
                lot_number="L-CONCORRENTE",
                origin="PRODUCTION",
                received_at=received_at,
            )
            barrier.wait()
            try:
                codes.append(SampleService(session).create(data, actor).sample_code)
            except Exception as error:
                errors.append(repr(error))

    threads = [threading.Thread(target=register) for _ in range(registrations)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    prefix = f"SMP-{received_at.year}-"
    assert all(code.startswith(prefix) for code in codes)
    numbers = sorted(int(code.removeprefix(prefix)) for code in codes)
    assert numbers == list(range(numbers[0], numbers[0] + registrations))
    with factory() as session:
        assert AuditService(session).verify().valid is True
