"""Dados de demonstração: gerados pelos serviços, coerentes e utilizáveis pela API."""

import json
import stat
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cli import __main__ as cli
from app.cli.demo import DemoDataError, DemoSummary, seed_demo
from app.core.config import Settings
from app.database.base import Base
from app.database.session import build_engine, build_session_factory
from app.domain.permissions import ROLE_DEFINITIONS
from app.models import (
    AuditLog,
    Client,
    Instrument,
    InstrumentResult,
    Product,
    Role,
    Sample,
    TestDefinition,
    TestResult,
    User,
)
from app.services.audit_service import AuditService

from .conftest import API

PASSWORD = "Demo@2026"


def _create_schema(session: Session) -> None:
    Base.metadata.create_all(session.get_bind())
    session.add_all(
        Role(code=code, name=name, description=description)
        for code, (name, description) in ROLE_DEFINITIONS.items()
    )
    session.commit()


@pytest.fixture
def demo(app: FastAPI, client: TestClient) -> Iterator[tuple[Session, DemoSummary]]:
    # Depende do client para ser encerrado antes dele (o client descarta o engine).
    with app.state.session_factory() as session:
        _create_schema(session)
        yield session, seed_demo(session, PASSWORD)


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_demo_has_the_planned_volume_and_variety(demo: tuple[Session, DemoSummary]) -> None:
    session, summary = demo

    assert {
        model.__name__: _count(session, model)
        for model in (Sample, Product, Client, User, Instrument, TestDefinition)
    } == {
        "Sample": 20,
        "Product": 5,
        "Client": 4,
        "User": 5,
        "Instrument": 6,
        "TestDefinition": 8,
    }
    assert summary.samples_by_status == {
        "APPROVED": 10,
        "AWAITING_REVIEW": 3,
        "CANCELLED": 1,
        "IN_ANALYSIS": 3,
        "RECEIVED": 1,
        "REJECTED": 2,
    }
    assert summary.rejected_messages == {
        "CALIBRATION_EXPIRED": 2,
        "INSTRUMENT_NOT_ACTIVE": 1,
        "SAMPLE_NOT_IN_ANALYSIS": 1,
        "TEST_ALREADY_COMPLETED": 1,
        "UNIT_MISMATCH": 1,
    }
    assert summary.admin_created is True
    assert set(summary.instrument_keys) == {
        "PH-METER-01",
        "PH-METER-02",
        "DENS-01",
        "KF-01",
        "HPLC-01",
        "VISC-01",
    }

    results = Counter(session.execute(select(TestResult.source, TestResult.spec_status)).all())
    assert {source for source, _ in results} == {"INSTRUMENT", "MANUAL"}
    assert sum(total for (_, status), total in results.items() if status == "OOS") >= 4
    corrected = session.scalars(select(TestResult).where(TestResult.version > 1)).all()
    assert len(corrected) == 3
    assert all(result.change_reason for result in corrected)
    messages = Counter(session.scalars(select(InstrumentResult.status)))
    assert messages["ACCEPTED"] > 20
    assert messages["REJECTED"] == 6


def test_demo_history_is_chronological_and_verifiable(demo: tuple[Session, DemoSummary]) -> None:
    session, _ = demo
    events = session.scalars(select(AuditLog).order_by(AuditLog.id)).all()

    assert AuditService(session).verify().valid is True
    moments = [event.occurred_at.replace(tzinfo=UTC) for event in events]
    assert moments == sorted(moments)
    assert moments[-1] <= datetime.now(UTC)
    assert (moments[-1] - moments[0]).days >= 45

    samples = session.scalars(select(Sample).order_by(Sample.received_at)).all()
    assert [s.sample_code for s in samples] == sorted(s.sample_code for s in samples)
    for sample in samples:
        first = next(event for event in events if event.sample_id == sample.id)
        assert first.action == "SAMPLE_CREATED"
        assert first.user_id == sample.created_by_id


def test_demo_respects_segregation_of_duties(demo: tuple[Session, DemoSummary]) -> None:
    session, _ = demo
    reviewer = session.scalar(select(User).where(User.username == "ana.souza"))
    assert reviewer is not None

    reviewed = session.scalars(select(Sample).where(Sample.reviewed_by_id.is_not(None))).all()
    assert len(reviewed) == 12
    assert {sample.reviewed_by_id for sample in reviewed} == {reviewer.id}
    authors = session.scalars(select(TestResult.entered_by_id).distinct()).all()
    assert reviewer.id not in authors
    # Toda amostra aprovada terminou sem OOS vigente, mesmo as que tiveram OOS corrigido.
    approved_with_oos_history = session.scalars(
        select(Sample.sample_code)
        .join(Sample.tests)
        .join(TestResult)
        .where(Sample.status == "APPROVED", TestResult.spec_status == "OOS")
        .distinct()
    ).all()
    assert len(approved_with_oos_history) == 2
    current_oos = session.scalars(
        select(Sample.sample_code)
        .join(Sample.tests)
        .join(TestResult)
        .where(Sample.status == "APPROVED", TestResult.is_current, TestResult.spec_status == "OOS")
    ).all()
    assert current_oos == []


def test_demo_users_and_instrument_keys_work_through_the_api(
    demo: tuple[Session, DemoSummary], client: TestClient
) -> None:
    _, summary = demo
    for username, _ in summary.users:
        response = client.post(
            f"{API}/auth/login", data={"username": username, "password": PASSWORD}
        )
        assert response.status_code == 200, username

    def worklist(code: str) -> tuple[int, dict]:
        response = client.get(
            f"{API}/instruments/worklist",
            headers={"X-Instrument-Key": summary.instrument_keys[code]},
        )
        return response.status_code, response.json()

    status, body = worklist("PH-METER-01")
    assert status == 200
    assert [item["priority"] for item in body["items"]][:1] == ["URGENT"]
    assert {item["test"] for item in body["items"]} == {"PH"}
    for code in ("HPLC-01", "KF-01", "DENS-01"):  # HPLC-01 usa a chave rotacionada
        status, body = worklist(code)
        assert status == 200 and body["items"], code
    assert worklist("VISC-01")[1]["error"]["code"] == "CALIBRATION_EXPIRED"
    assert worklist("PH-METER-02")[1]["error"]["code"] == "INSTRUMENT_NOT_ACTIVE"


def test_demo_refuses_a_database_with_data(demo: tuple[Session, DemoSummary]) -> None:
    session, _ = demo
    with pytest.raises(DemoDataError, match="já contém dados"):
        seed_demo(session, PASSWORD)


def test_cli_writes_simulator_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'demo.db'}"
    engine = build_engine(url)
    with build_session_factory(engine)() as session:
        _create_schema(session)
    engine.dispose()
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(database_url=url, _env_file=None))
    monkeypatch.delenv("LABTRACK_DEMO_PASSWORD", raising=False)
    config_path = tmp_path / "simulator" / "config.json"

    cli.main(["seed-demo", "--simulator-config", str(config_path), "--api-url", "http://api/v1"])

    output = capsys.readouterr().out
    assert "Senha de todos: Demo@2026" in output
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["api_url"] == "http://api/v1"
    assert [item["code"] for item in config["instruments"]][:2] == ["PH-METER-01", "PH-METER-02"]
    assert all(item["key"].startswith("lt_inst_") for item in config["instruments"])
    assert stat.S_IMODE(config_path.stat().st_mode) == 0o600


def test_cli_refuses_demo_data_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    production = Settings(environment="production", _env_file=None)
    monkeypatch.setattr(cli, "get_settings", lambda: production)
    with pytest.raises(SystemExit, match="produção"):
        cli.main(["seed-demo"])
