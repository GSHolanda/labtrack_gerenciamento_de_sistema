"""Simulador contra a API real do LabTrack (em processo, SQLite em memória).

Roda quando o backend está instalado no mesmo ambiente
(``pip install -e ../backend -e .[dev]``); caso contrário é pulado.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("app.main", reason="backend do LabTrack não instalado")

from app.cli.demo import DemoSummary, seed_demo
from app.core.config import Settings
from app.database.base import Base
from app.domain.permissions import ROLE_DEFINITIONS
from app.main import create_app
from app.models import InstrumentResult, Role, SampleTest, TestResult
from fastapi.testclient import TestClient
from sqlalchemy import select

from simulator.__main__ import main


@dataclass
class Lab:
    client: TestClient
    summary: DemoSummary
    session_factory: Any
    config: Path

    def run(self, *args: str) -> int:
        return main([*args, "--config", str(self.config)], http=self.client)

    def pending(self, test: str) -> int:
        """Testes pendentes em amostras em análise (os que entram na worklist)."""
        with self.session_factory() as session:
            return len(
                session.scalars(
                    select(SampleTest)
                    .join(SampleTest.test_definition)
                    .where(SampleTest.status == "PENDING")
                    .where(SampleTest.test_definition.has(code=test))
                    .where(SampleTest.sample.has(status="IN_ANALYSIS"))
                ).all()
            )

    def instrument_results(self) -> list[TestResult]:
        with self.session_factory() as session:
            return list(
                session.scalars(select(TestResult).where(TestResult.source == "INSTRUMENT"))
            )


@pytest.fixture
def lab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Lab]:
    monkeypatch.setattr("app.core.security.BCRYPT_ROUNDS", 4)
    settings = Settings(
        environment="test", database_url="sqlite+pysqlite:///:memory:", _env_file=None
    )
    app = create_app(settings)
    with TestClient(app) as client:
        with app.state.session_factory() as session:
            Base.metadata.create_all(session.get_bind())
            session.add_all(
                Role(code=code, name=name, description=description)
                for code, (name, description) in ROLE_DEFINITIONS.items()
            )
            session.commit()
            summary = seed_demo(session, "Demo@2026")
        config = tmp_path / "config.json"
        config.write_text(
            json.dumps(
                {
                    "api_url": "/api/v1",
                    "instruments": [
                        {"code": code, "key": key} for code, key in summary.instrument_keys.items()
                    ],
                }
            ),
            encoding="utf-8",
        )
        yield Lab(client, summary, app.state.session_factory, config)


def test_one_cycle_measures_every_pending_instrument_test(
    lab: Lab, capsys: pytest.CaptureFixture[str]
) -> None:
    before = {test: lab.pending(test) for test in ("PH", "DENSITY", "ASSAY", "MOISTURE")}
    assert all(before.values())
    instrument_results = len(lab.instrument_results())

    assert lab.run("run", "--once", "--oos-rate", "0", "--seed", "1") == 0

    output = capsys.readouterr().out
    assert {test: lab.pending(test) for test in before} == dict.fromkeys(before, 0)
    measured = lab.instrument_results()[instrument_results:]
    assert len(measured) == sum(before.values())
    assert {result.spec_status for result in measured} == {"IN_SPEC"}
    # Viscosímetro com calibração vencida e pHmetro em manutenção não medem.
    assert lab.pending("VISCOSITY") == 1
    assert "[VISC-01] worklist indisponível: CALIBRATION_EXPIRED" in output
    assert "[PH-METER-02] worklist indisponível: INSTRUMENT_NOT_ACTIVE" in output
    assert "[VISC-01] conectado, mas sem liberar medições (calibração vencida)" in output
    assert f"Resumo: {sum(before.values())} aceitos (0 OOS), 0 recusados." in output

    assert lab.run("run", "--once", "--instrument", "PH-METER-01") == 0
    assert "[PH-METER-01] nenhum teste pendente" in capsys.readouterr().out


def test_oos_rate_one_produces_only_oos_results(lab: Lab) -> None:
    before = len(lab.instrument_results())

    assert lab.run("run", "--once", "--oos-rate", "1", "--instrument", "HPLC-01") == 0

    measured = lab.instrument_results()[before:]
    assert measured
    assert {result.spec_status for result in measured} == {"OOS"}


def test_send_reports_rejections_with_message_id(
    lab: Lab, capsys: pytest.CaptureFixture[str]
) -> None:
    lab.run("worklist", "--instrument", "PH-METER-01")
    worklist = capsys.readouterr().out
    sample = worklist.split()[worklist.split().index("URGENT") + 1]

    wrong_unit = ["send", "--instrument", "PH-METER-01", "--sample", sample, "--test", "PH"]
    assert lab.run(*wrong_unit, "--value", "6.1", "--unit", "mV") == 1
    rejected = capsys.readouterr().out
    assert "Recusado: UNIT_MISMATCH (HTTP 422)" in rejected
    with lab.session_factory() as session:
        last = session.scalars(
            select(InstrumentResult).order_by(InstrumentResult.id.desc())
        ).first()
        assert last is not None and last.status == "REJECTED"
        assert f"mensagem {last.id}" in rejected

    assert lab.run(*wrong_unit, "--value", "6.1", "--unit", "pH", "--as-instrument", "X-9") == 1
    assert "INSTRUMENT_ID_MISMATCH (HTTP 403)" in capsys.readouterr().out

    assert lab.run(*wrong_unit, "--value", "6.1", "--unit", "pH") == 0
    assert "IN_SPEC" in capsys.readouterr().out


def test_heartbeat_and_configuration_errors(lab: Lab, capsys: pytest.CaptureFixture[str]) -> None:
    assert lab.run("heartbeat", "--instrument", "VISC-01", "--instrument", "HPLC-01") == 0
    output = capsys.readouterr().out
    assert "[VISC-01] ACTIVE" in output and "não pode medir" in output
    assert "[HPLC-01] ACTIVE" in output and "pode medir" in output

    assert lab.run("heartbeat", "--instrument", "BALANCE-01") == 2
    assert "BALANCE-01" in capsys.readouterr().err

    invalid = main(
        ["heartbeat", "--config", "/nao/existe.json", "--key", "PH-METER-01=lt_inst_x"],
        http=lab.client,
    )
    assert invalid == 1
    assert "INVALID_INSTRUMENT_KEY" in capsys.readouterr().out
