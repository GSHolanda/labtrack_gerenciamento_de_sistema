"""Testes que dependem de recursos do PostgreSQL (triggers, migrações reais)."""

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from app.database.session import build_session_factory
from app.models import AuditLog

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
