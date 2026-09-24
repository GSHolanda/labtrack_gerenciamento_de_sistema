"""Dashboard pelo contrato HTTP: permissões, carga atual, período e séries."""

from datetime import UTC, date, datetime
from typing import Any

import pytest

from ..conftest import DEFAULT_PASSWORD
from .conftest import API, Lab


def _get(lab: Lab, path: str, **params: Any) -> dict[str, Any]:
    response = lab.client.get(f"{API}/dashboard/{path}", headers=lab.manager, params=params)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def scenario(lab: Lab) -> Lab:
    """Uma amostra em cada situação relevante para os indicadores."""
    approved = lab.create_sample(priority="NORMAL")
    lab.analyze(approved)
    lab.submit(approved)
    response = lab.post(
        f"/samples/{approved['id']}/approve", lab.reviewer, {"password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 200, response.text

    rejected = lab.create_sample(priority="NORMAL")
    lab.analyze(rejected, {"PH": "8.0", "DENSITY": "1.02"})  # PH fora (5.5 a 7.0)
    lab.submit(rejected)
    response = lab.post(
        f"/samples/{rejected['id']}/reject", lab.reviewer, {"reason": "pH fora da especificação"}
    )
    assert response.status_code == 200, response.text

    urgent_oos = lab.create_sample(priority="URGENT")
    lab.analyze(urgent_oos, {"PH": "4.9"})  # em análise, com OOS vigente

    cancelled = lab.create_sample(priority="NORMAL")
    response = lab.post(
        f"/samples/{cancelled['id']}/cancel", lab.manager, {"reason": "Registro duplicado"}
    )
    assert response.status_code == 200, response.text

    lab.create_sample(priority="NORMAL")  # apenas recebida
    return lab


@pytest.mark.parametrize("role", ["admin", "analyst", "reviewer", "manager"])
@pytest.mark.parametrize("path", ["summary", "charts"])
def test_every_profile_views_the_dashboard(lab: Lab, role: str, path: str) -> None:
    response = lab.client.get(f"{API}/dashboard/{path}", headers=getattr(lab, role))
    assert response.status_code == 200


@pytest.mark.parametrize("path", ["summary", "charts"])
def test_dashboard_requires_authentication_and_valid_period(lab: Lab, path: str) -> None:
    assert lab.client.get(f"{API}/dashboard/{path}").status_code == 401
    for days in (0, 367):
        response = lab.client.get(
            f"{API}/dashboard/{path}", headers=lab.analyst, params={"period_days": days}
        )
        assert response.status_code == 422


def test_summary_reports_workload_and_period_totals(scenario: Lab) -> None:
    summary = _get(scenario, "summary", period_days=30)

    assert summary["workload"] == {
        "open": 2,
        "received": 1,
        "in_analysis": 1,
        "awaiting_review": 0,
        "open_with_oos": 1,
        "urgent_open": 1,
    }
    current = summary["current"]
    assert {key: current[key] for key in ("received", "approved", "rejected", "cancelled")} == {
        "received": 5,
        "approved": 1,
        "rejected": 1,
        "cancelled": 1,
    }
    assert current["approval_rate"] == 0.5
    # Recebidas 1 h antes do registro (fixture); decididas logo em seguida.
    assert current["average_processing_hours"] == pytest.approx(1.0, abs=0.1)
    assert current["median_processing_hours"] == pytest.approx(1.0, abs=0.1)
    assert (current["oos_results"], current["samples_with_oos"]) == (2, 2)
    assert summary["previous"]["approved"] == 0
    assert summary["previous"]["approval_rate"] is None
    assert summary["period"]["days"] == 30
    assert summary["period"]["timezone"] == "America/Sao_Paulo"


def test_corrected_oos_still_counts_in_the_period(scenario: Lab) -> None:
    sample = scenario.create_sample(priority="NORMAL")
    scenario.analyze(sample, {"PH": "7.9"})
    assert scenario.enter(sample, "PH", "6.8", "Erro de transcrição").status_code == 201

    summary = _get(scenario, "summary")
    assert summary["workload"]["open_with_oos"] == 1  # só a amostra urgente segue com OOS vigente
    assert summary["current"]["oos_results"] == 3  # o OOS corrigido não some da estatística


def test_charts_series_by_status_and_oos_by_test(scenario: Lab) -> None:
    charts = _get(scenario, "charts", period_days=30)

    assert charts["granularity"] == "day"
    throughput = charts["throughput"]
    assert len(throughput) in (30, 31, 32)
    days = [date.fromisoformat(point["bucket"]) for point in throughput]
    assert days == sorted(days) and len(set(days)) == len(days)
    assert sum(point["approved"] for point in throughput) == 1
    assert sum(point["rejected"] for point in throughput) == 1
    decided = [point for point in throughput if point["approved"] or point["rejected"]]
    assert decided[0]["approval_rate"] == 0.5
    assert all(point["approval_rate"] is None for point in throughput if point not in decided)

    assert {item["status"]: item["count"] for item in charts["by_status"]} == {
        "RECEIVED": 1,
        "IN_ANALYSIS": 1,
        "AWAITING_REVIEW": 0,
        "APPROVED": 1,
        "REJECTED": 1,
        "CANCELLED": 1,
    }
    ph, density = charts["oos_by_test"]
    assert (ph["test_code"], ph["results"], ph["oos"]) == ("PH", 3, 2)
    assert ph["oos_rate"] == pytest.approx(0.6667)
    assert (density["test_code"], density["oos"]) == ("DENSITY", 0)


@pytest.mark.parametrize(("days", "granularity"), [(7, "day"), (90, "week"), (365, "month")])
def test_granularity_follows_the_period(lab: Lab, days: int, granularity: str) -> None:
    charts = _get(lab, "charts", period_days=days)
    assert charts["granularity"] == granularity
    start = datetime.fromisoformat(charts["period"]["start"])
    end = datetime.fromisoformat(charts["period"]["end"])
    if start.tzinfo is None:
        start, end = start.replace(tzinfo=UTC), end.replace(tzinfo=UTC)
    assert (end - start).days == days


def test_reading_the_dashboard_does_not_write_audit(scenario: Lab) -> None:
    before = scenario.client.get(f"{API}/audit-logs", headers=scenario.manager).json()["total"]
    _get(scenario, "summary")
    _get(scenario, "charts")
    after = scenario.client.get(f"{API}/audit-logs", headers=scenario.manager).json()["total"]
    assert after == before
