"""Cenário de laboratório montado pela própria API (como um usuário faria)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.domain.enums import RoleCode

from ..conftest import LoginAs

API = "/api/v1"


@dataclass
class Lab:
    client: TestClient
    admin: dict[str, str]
    analyst: dict[str, str]
    reviewer: dict[str, str]
    manager: dict[str, str]
    client_id: int
    product_id: int
    tests: dict[str, int]  # código do teste -> id

    def post(self, path: str, headers: dict[str, str], json: Any = None) -> Any:
        return self.client.post(f"{API}{path}", json=json, headers=headers)

    def create_sample(self, **overrides: Any) -> dict[str, Any]:
        payload = {
            "product_id": self.product_id,
            "client_id": self.client_id,
            "lot_number": "L2026-0915",
            "origin": "PRODUCTION",
            "received_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
            "priority": "HIGH",
            **overrides,
        }
        response = self.post("/samples", self.analyst, payload)
        assert response.status_code == 201, response.text
        return response.json()

    def get_sample(self, sample_id: int) -> dict[str, Any]:
        return self.client.get(f"{API}/samples/{sample_id}", headers=self.analyst).json()

    def test_id(self, sample: dict[str, Any], code: str) -> int:
        return next(t["id"] for t in sample["tests"] if t["test_code"] == code)

    def enter(
        self, sample: dict[str, Any], code: str, value: Any, reason: str | None = None
    ) -> Any:
        payload: dict[str, Any] = {"value": value}
        if reason is not None:
            payload["change_reason"] = reason
        return self.post(
            f"/sample-tests/{self.test_id(sample, code)}/results", self.analyst, payload
        )

    def analyze(
        self, sample: dict[str, Any], values: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Inicia a análise e lança resultados (por padrão, todos dentro da especificação)."""
        values = IN_SPEC_VALUES if values is None else values
        response = self.post(f"/samples/{sample['id']}/start-analysis", self.analyst)
        assert response.status_code == 200, response.text
        for code, value in values.items():
            result = self.enter(sample, code, value)
            assert result.status_code == 201, result.text
        return self.get_sample(sample["id"])

    def submit(self, sample: dict[str, Any]) -> dict[str, Any]:
        response = self.post(f"/samples/{sample['id']}/submit-for-review", self.analyst)
        assert response.status_code == 200, response.text
        return response.json()


# Produto PRD-001: pH 5.5-7.0 (limite do produto) e densidade 1.00-1.05 (padrão).
IN_SPEC_VALUES = {"PH": "6.8", "DENSITY": "1.02"}

TEST_DEFINITIONS = [
    {
        "code": "PH",
        "name": "pH",
        "unit": "pH",
        "spec_min": 6.5,
        "spec_max": 7.5,
        "method": "Potenciometria",
        "instrument_type": "PH_METER",
    },
    {
        "code": "DENSITY",
        "name": "Densidade",
        "unit": "g/mL",
        "spec_min": 1.0,
        "spec_max": 1.05,
        "method": "Densímetro digital",
        "instrument_type": "DENSITY_METER",
    },
    {
        "code": "MOISTURE",
        "name": "Umidade",
        "unit": "%",
        "spec_max": 0.5,
        "method": "Karl Fischer",
        "instrument_type": "MOISTURE_ANALYZER",
    },
]


@pytest.fixture
def lab(client: TestClient, login_as: LoginAs) -> Lab:
    admin = login_as(RoleCode.ADMIN)

    def create(path: str, payload: dict[str, Any]) -> int:
        response = client.post(f"{API}{path}", json=payload, headers=admin)
        assert response.status_code == 201, response.text
        return response.json()["id"]

    client_id = create("/clients", {"code": "CLI-001", "name": "Farmacêutica Aurora"})
    product_id = create(
        "/products", {"code": "PRD-001", "name": "Xampu Neutro", "category": "Cosmético"}
    )
    tests = {item["code"]: create("/test-definitions", item) for item in TEST_DEFINITIONS}

    # Plano analítico do produto: pH (com limite próprio) e densidade.
    response = client.put(
        f"{API}/products/{product_id}/specifications",
        json=[
            {"test_definition_id": tests["PH"], "spec_min": 5.5, "spec_max": 7.0},
            {"test_definition_id": tests["DENSITY"]},
        ],
        headers=admin,
    )
    assert response.status_code == 200, response.text

    return Lab(
        client=client,
        admin=admin,
        analyst=login_as(RoleCode.ANALYST),
        reviewer=login_as(RoleCode.REVIEWER),
        manager=login_as(RoleCode.MANAGER),
        client_id=client_id,
        product_id=product_id,
        tests=tests,
    )
