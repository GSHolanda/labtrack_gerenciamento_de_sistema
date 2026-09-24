from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.audit import AuditAction
from app.models import AuditLog

from .conftest import API, Lab


def _last_audit(db: Session, action: AuditAction) -> AuditLog:
    db.expire_all()
    return db.scalars(
        select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id.desc())
    ).first()  # type: ignore[return-value]


@pytest.mark.parametrize("path", ["/clients", "/products", "/test-definitions"])
def test_only_admin_manages_master_data(lab: Lab, path: str) -> None:
    response = lab.post(path, lab.analyst, {"code": "X1", "name": "Qualquer"})
    assert response.status_code == 403


def test_every_authenticated_user_can_read_master_data(lab: Lab) -> None:
    for path in ("/clients", "/products", "/test-definitions"):
        response = lab.client.get(f"{API}{path}", headers=lab.reviewer)
        assert response.status_code == 200
        assert response.json()["total"] >= 1


def test_duplicate_codes_are_rejected(lab: Lab) -> None:
    response = lab.post("/clients", lab.admin, {"code": "cli-001", "name": "Outro"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATED_CLIENTE"


@pytest.mark.parametrize(
    "limits",
    [{"spec_min": 8, "spec_max": 7}, {}],
    ids=["min-maior-que-max", "sem-limites"],
)
def test_test_definition_limits_are_validated(lab: Lab, limits: dict[str, float]) -> None:
    payload = {
        "code": "VISC",
        "name": "Viscosidade",
        "unit": "cP",
        "method": "Rotacional",
        **limits,
    }

    assert lab.post("/test-definitions", lab.admin, payload).status_code == 422


def test_test_definition_code_cannot_be_changed(lab: Lab) -> None:
    response = lab.client.patch(
        f"{API}/test-definitions/{lab.tests['PH']}", json={"code": "PH2"}, headers=lab.admin
    )
    assert response.status_code == 422


def test_limit_change_is_audited_with_old_and_new_values(lab: Lab, db: Session) -> None:
    response = lab.client.patch(
        f"{API}/test-definitions/{lab.tests['PH']}", json={"spec_max": 8.0}, headers=lab.admin
    )

    assert response.status_code == 200
    entry = _last_audit(db, AuditAction.TEST_DEFINITION_UPDATED)
    assert entry.old_value == {"spec_max": "7.5"}
    assert entry.new_value == {"spec_max": "8"}


def test_update_rejects_limits_inverted_by_partial_change(lab: Lab) -> None:
    response = lab.client.patch(
        f"{API}/test-definitions/{lab.tests['PH']}", json={"spec_min": 9}, headers=lab.admin
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_SPECIFICATION"


def test_product_specification_shows_effective_limits(lab: Lab) -> None:
    specs = lab.client.get(
        f"{API}/products/{lab.product_id}/specifications", headers=lab.analyst
    ).json()

    by_code = {spec["test_code"]: spec for spec in specs}
    assert set(by_code) == {"PH", "DENSITY"}
    assert Decimal(by_code["PH"]["spec_min"]) == Decimal("5.5")  # limite do produto
    assert by_code["PH"]["overrides_default"] is True
    assert Decimal(by_code["DENSITY"]["spec_max"]) == Decimal("1.05")  # padrão do teste


def test_inactive_test_cannot_enter_a_plan(lab: Lab) -> None:
    lab.client.patch(
        f"{API}/test-definitions/{lab.tests['MOISTURE']}",
        json={"is_active": False},
        headers=lab.admin,
    )
    response = lab.client.put(
        f"{API}/products/{lab.product_id}/specifications",
        json=[{"test_definition_id": lab.tests["MOISTURE"]}],
        headers=lab.admin,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_TEST_DEFINITION"


def test_plan_change_is_audited(lab: Lab, db: Session) -> None:
    entry = _last_audit(db, AuditAction.SPECIFICATION_UPDATED)

    assert entry.old_value == []
    assert [item["test"] for item in entry.new_value] == ["DENSITY", "PH"]


def test_master_data_search(lab: Lab) -> None:
    page = lab.client.get(
        f"{API}/test-definitions", params={"q": "umid"}, headers=lab.analyst
    ).json()

    assert [item["code"] for item in page["items"]] == ["MOISTURE"]
