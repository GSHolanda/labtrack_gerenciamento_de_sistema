from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.audit import AuditAction
from app.models import AuditLog, User

from .conftest import API, IN_SPEC_VALUES, Lab


def _audit_actions(db: Session, sample_id: int) -> list[str]:
    db.expire_all()
    return list(
        db.scalars(
            select(AuditLog.action).where(AuditLog.sample_id == sample_id).order_by(AuditLog.id)
        )
    )


def _action(lab: Lab, sample_id: int, action: str, headers: dict[str, str], json=None):  # type: ignore[no-untyped-def]
    return lab.post(f"/samples/{sample_id}/{action}", headers, json)


# --- Registro -----------------------------------------------------------------


@pytest.mark.rules("RN-01")
def test_register_generates_sequential_code_per_year(lab: Lab) -> None:
    year = datetime.now(UTC).year
    first = lab.create_sample()
    second = lab.create_sample()

    assert first["sample_code"] == f"SMP-{year}-0001"
    assert second["sample_code"] == f"SMP-{year}-0002"
    assert first["status"] == "RECEIVED"


@pytest.mark.rules("RN-01")
def test_code_sequence_restarts_each_year(lab: Lab) -> None:
    lab.create_sample()
    last_year = lab.create_sample(received_at="2025-06-01T10:00:00+00:00")

    assert last_year["sample_code"] == "SMP-2025-0001"


@pytest.mark.rules("RN-04", "RN-06")
def test_product_plan_is_assigned_with_limit_snapshot(lab: Lab) -> None:
    sample = lab.create_sample()

    tests = {test["test_code"]: test for test in sample["tests"]}
    assert set(tests) == {"PH", "DENSITY"}
    assert Decimal(tests["PH"]["spec_min"]) == Decimal("5.5")  # limite do produto
    assert Decimal(tests["PH"]["spec_max"]) == Decimal("7.0")
    assert all(test["status"] == "PENDING" for test in tests.values())
    assert sample["allowed_actions"] == ["start_analysis", "cancel"]


@pytest.mark.rules("RN-06")
def test_later_limit_change_does_not_affect_existing_sample(lab: Lab) -> None:
    sample = lab.create_sample()
    lab.client.patch(
        f"{API}/test-definitions/{lab.tests['DENSITY']}", json={"spec_max": 2.0}, headers=lab.admin
    )

    refreshed = lab.client.get(f"{API}/samples/{sample['id']}", headers=lab.analyst).json()
    density = next(t for t in refreshed["tests"] if t["test_code"] == "DENSITY")
    assert Decimal(density["spec_max"]) == Decimal("1.05")


def test_registration_is_audited(lab: Lab, db: Session) -> None:
    sample = lab.create_sample()

    assert _audit_actions(db, sample["id"]) == ["SAMPLE_CREATED", "TESTS_ASSIGNED"]


@pytest.mark.rules("RN-02", "RN-03")
@pytest.mark.parametrize(
    ("override", "code"),
    [
        (
            {"received_at": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
            "RECEIVED_AT_IN_FUTURE",
        ),
        ({"product_id": 999}, "INVALID_PRODUCT"),
        ({"client_id": 999}, "INVALID_CLIENT"),
    ],
)
def test_registration_rules(lab: Lab, override: dict[str, object], code: str) -> None:
    response = lab.post(
        "/samples",
        lab.analyst,
        {
            "product_id": lab.product_id,
            "client_id": lab.client_id,
            "lot_number": "L1",
            "origin": "PRODUCTION",
            "received_at": datetime.now(UTC).isoformat(),
            **override,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


@pytest.mark.rules("RN-02")
def test_inactive_product_cannot_receive_samples(lab: Lab) -> None:
    lab.client.patch(
        f"{API}/products/{lab.product_id}", json={"is_active": False}, headers=lab.admin
    )

    response = lab.post(
        "/samples",
        lab.analyst,
        {
            "product_id": lab.product_id,
            "client_id": lab.client_id,
            "lot_number": "L1",
            "origin": "PRODUCTION",
            "received_at": datetime.now(UTC).isoformat(),
        },
    )
    assert response.json()["error"]["code"] == "INVALID_PRODUCT"


def test_responsible_must_be_an_analyst(lab: Lab, db: Session) -> None:
    reviewer_id = db.scalars(select(User.id).where(User.username == "ana.souza")).one()
    analyst_id = db.scalars(select(User.id).where(User.username == "carlos.silva")).one()

    ok = lab.create_sample(responsible_id=analyst_id)
    assert ok["responsible"]["full_name"] == "Carlos Silva"

    response = lab.post(
        "/samples",
        lab.analyst,
        {
            "product_id": lab.product_id,
            "client_id": lab.client_id,
            "lot_number": "L1",
            "origin": "PRODUCTION",
            "received_at": datetime.now(UTC).isoformat(),
            "responsible_id": reviewer_id,
        },
    )
    assert response.json()["error"]["code"] == "INVALID_RESPONSIBLE"


@pytest.mark.parametrize("role", ["reviewer", "manager", "admin"])
def test_only_analysts_register_samples(lab: Lab, role: str) -> None:
    response = lab.post("/samples", getattr(lab, role), {})
    assert response.status_code == 403


# --- Testes atribuídos --------------------------------------------------------


@pytest.mark.rules("RN-05")
def test_assign_additional_test(lab: Lab, db: Session) -> None:
    sample = lab.create_sample()
    response = lab.post(
        f"/samples/{sample['id']}/tests",
        lab.analyst,
        {"test_definition_ids": [lab.tests["MOISTURE"]]},
    )

    assert response.status_code == 200
    assert {t["test_code"] for t in response.json()["tests"]} == {"PH", "DENSITY", "MOISTURE"}


@pytest.mark.rules("RN-05")
def test_same_test_cannot_be_assigned_twice(lab: Lab) -> None:
    sample = lab.create_sample()
    response = lab.post(
        f"/samples/{sample['id']}/tests", lab.analyst, {"test_definition_ids": [lab.tests["PH"]]}
    )

    assert response.status_code == 409
    assert response.json()["error"]["details"]["tests"] == ["PH"]


@pytest.mark.rules("RN-07")
def test_cancel_pending_test_requires_reason(lab: Lab, db: Session) -> None:
    sample = lab.create_sample()
    test_id = sample["tests"][0]["id"]

    assert (
        lab.post(f"/sample-tests/{test_id}/cancel", lab.analyst, {"reason": ""}).status_code == 422
    )
    response = lab.post(
        f"/sample-tests/{test_id}/cancel", lab.analyst, {"reason": "Atribuído por engano"}
    )
    assert response.status_code == 200
    assert response.json()["tests"][0]["status"] == "CANCELLED"
    assert "TEST_CANCELLED" in _audit_actions(db, sample["id"])

    again = lab.post(
        f"/sample-tests/{test_id}/cancel", lab.analyst, {"reason": "De novo, por engano"}
    )
    assert again.json()["error"]["code"] == "SAMPLE_TEST_NOT_PENDING"


# --- Workflow -----------------------------------------------------------------


@pytest.mark.rules("RN-08")
def test_analysis_requires_assigned_tests(lab: Lab) -> None:
    lab.client.put(f"{API}/products/{lab.product_id}/specifications", json=[], headers=lab.admin)
    sample = lab.create_sample()

    response = _action(lab, sample["id"], "start-analysis", lab.analyst)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NO_TESTS_ASSIGNED"


@pytest.mark.rules("RN-10", "RN-15")
def test_full_flow_until_review_with_history(lab: Lab, db: Session) -> None:
    sample = lab.create_sample()

    started = _action(lab, sample["id"], "start-analysis", lab.analyst)
    assert started.json()["status"] == "IN_ANALYSIS"

    pending = _action(lab, sample["id"], "submit-for-review", lab.analyst)
    assert pending.status_code == 409
    assert set(pending.json()["error"]["details"]["tests"]) == {"PH", "DENSITY"}

    for code, value in IN_SPEC_VALUES.items():
        assert lab.enter(sample, code, value).status_code == 201
    submitted = _action(lab, sample["id"], "submit-for-review", lab.analyst).json()
    assert submitted["status"] == "AWAITING_REVIEW"
    assert submitted["submitted_at"] is not None
    assert submitted["allowed_actions"] == ["approve", "reject", "return_to_analysis", "cancel"]

    history = lab.client.get(
        f"{API}/samples/{sample['id']}/status-history", headers=lab.reviewer
    ).json()
    assert [(h["from_status"], h["to_status"]) for h in history] == [
        (None, "RECEIVED"),
        ("RECEIVED", "IN_ANALYSIS"),
        ("IN_ANALYSIS", "AWAITING_REVIEW"),
    ]
    assert history[1]["changed_by"]["full_name"] == "Carlos Silva"
    assert _audit_actions(db, sample["id"]).count("SAMPLE_STATUS_CHANGED") == 2


@pytest.mark.rules("RN-05", "RN-11")
def test_sample_is_locked_while_awaiting_review(lab: Lab, db: Session) -> None:
    sample = lab.create_sample()
    lab.analyze(sample)
    current = lab.submit(sample)

    edit = lab.client.patch(
        f"{API}/samples/{sample['id']}",
        json={"version": current["version"], "notes": "x"},
        headers=lab.analyst,
    )
    assert edit.json()["error"]["code"] == "SAMPLE_NOT_EDITABLE"
    assign = lab.post(
        f"/samples/{sample['id']}/tests",
        lab.analyst,
        {"test_definition_ids": [lab.tests["MOISTURE"]]},
    )
    assert assign.json()["error"]["code"] == "SAMPLE_NOT_EDITABLE"


@pytest.mark.rules("RN-15")
def test_invalid_transition_is_rejected(lab: Lab) -> None:
    sample = lab.create_sample()
    _action(lab, sample["id"], "start-analysis", lab.analyst)

    response = _action(lab, sample["id"], "start-analysis", lab.analyst)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


@pytest.mark.rules("RN-13")
def test_cancellation_is_managerial_and_requires_reason(lab: Lab, db: Session) -> None:
    sample = lab.create_sample()

    assert (
        _action(lab, sample["id"], "cancel", lab.analyst, {"reason": "Duplicada"}).status_code
        == 403
    )
    assert _action(lab, sample["id"], "cancel", lab.manager, {}).status_code == 422

    cancelled = _action(
        lab, sample["id"], "cancel", lab.manager, {"reason": "Registro em duplicidade"}
    )
    body = cancelled.json()
    assert body["status"] == "CANCELLED"
    assert body["completed_at"] is not None
    assert body["allowed_actions"] == []

    after = _action(lab, sample["id"], "start-analysis", lab.analyst)
    assert after.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"

    history = lab.client.get(
        f"{API}/samples/{sample['id']}/status-history", headers=lab.manager
    ).json()
    assert history[-1]["reason"] == "Registro em duplicidade"
    assert history[-1]["changed_by"]["full_name"] == "Marcos Lima"


# --- Edição e concorrência ----------------------------------------------------


def test_edit_is_audited_with_changed_fields_only(lab: Lab, db: Session) -> None:
    sample = lab.create_sample()
    response = lab.client.patch(
        f"{API}/samples/{sample['id']}",
        json={"version": sample["version"], "priority": "URGENT", "lot_number": "L2026-0915"},
        headers=lab.analyst,
    )

    assert response.status_code == 200
    assert response.json()["version"] == sample["version"] + 1
    db.expire_all()
    entry = db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.SAMPLE_UPDATED)).one()
    assert entry.old_value == {"priority": "HIGH"}
    assert entry.new_value == {"priority": "URGENT"}


def test_stale_version_is_rejected(lab: Lab) -> None:
    sample = lab.create_sample()
    url = f"{API}/samples/{sample['id']}"
    lab.client.patch(url, json={"version": sample["version"], "notes": "A"}, headers=lab.analyst)

    response = lab.client.patch(
        url, json={"version": sample["version"], "notes": "B"}, headers=lab.analyst
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONCURRENT_MODIFICATION"


# --- Pesquisa -----------------------------------------------------------------


def test_search_filters(lab: Lab) -> None:
    first = lab.create_sample(lot_number="LOTE-A")
    lab.create_sample(lot_number="LOTE-B")
    _action(lab, first["id"], "start-analysis", lab.analyst)

    def search(**params: object) -> list[str]:
        response = lab.client.get(f"{API}/samples", params=params, headers=lab.reviewer)
        assert response.status_code == 200, response.text
        return [item["lot_number"] for item in response.json()["items"]]

    assert search(status="IN_ANALYSIS") == ["LOTE-A"]
    assert sorted(search(status=["IN_ANALYSIS", "RECEIVED"])) == ["LOTE-A", "LOTE-B"]
    assert search(lot_number="lote-b") == ["LOTE-B"]
    assert len(search(q="xampu")) == 2
    assert search(q="inexistente") == []
    assert search(code=first["sample_code"]) == ["LOTE-A"]
    assert search(sort="lot_number", size=1) == ["LOTE-A"]
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert search(received_from=tomorrow) == []


@pytest.mark.rules("RN-18")
def test_search_reports_progress_and_current_oos(lab: Lab) -> None:
    sample = lab.create_sample()
    _action(lab, sample["id"], "start-analysis", lab.analyst)
    assert lab.enter(sample, "PH", "8.0").status_code == 201  # OOS (produto: 5.5 a 7.0)

    def summary() -> dict[str, object]:
        response = lab.client.get(f"{API}/samples", headers=lab.analyst)
        item = response.json()["items"][0]
        return {key: item[key] for key in ("tests_total", "tests_completed", "has_oos")}

    assert summary() == {"tests_total": 2, "tests_completed": 1, "has_oos": True}
    corrected = lab.enter(sample, "PH", "6.8", reason="Erro de transcrição")
    assert corrected.status_code == 201
    assert summary() == {"tests_total": 2, "tests_completed": 1, "has_oos": False}
    cancelled = lab.post(
        f"/sample-tests/{lab.test_id(sample, 'DENSITY')}/cancel",
        lab.analyst,
        {"reason": "Não solicitado pelo cliente"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert summary() == {"tests_total": 1, "tests_completed": 1, "has_oos": False}
    detail = lab.get_sample(sample["id"])
    assert (detail["tests_total"], detail["tests_completed"]) == (1, 1)
    assert {t["test_code"]: t["decimal_places"] for t in detail["tests"]} == {
        "PH": 2,
        "DENSITY": 2,
    }


def test_priority_and_status_sort_follow_business_order(lab: Lab) -> None:
    for priority in ("HIGH", "LOW", "URGENT", "NORMAL"):
        sample = lab.create_sample(priority=priority)
        if priority in ("HIGH", "URGENT"):
            _action(lab, sample["id"], "start-analysis", lab.analyst)

    def order(sort: str, field: str) -> list[str]:
        response = lab.client.get(f"{API}/samples", params={"sort": sort}, headers=lab.analyst)
        return [item[field] for item in response.json()["items"]]

    assert order("-priority", "priority") == ["URGENT", "HIGH", "NORMAL", "LOW"]
    assert order("priority", "priority") == ["LOW", "NORMAL", "HIGH", "URGENT"]
    assert order("status", "status") == ["RECEIVED", "RECEIVED", "IN_ANALYSIS", "IN_ANALYSIS"]


def test_search_rejects_unknown_sort_field(lab: Lab) -> None:
    response = lab.client.get(f"{API}/samples", params={"sort": "password"}, headers=lab.analyst)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_SORT_FIELD"


def test_unknown_sample_returns_404(lab: Lab) -> None:
    response = lab.client.get(f"{API}/samples/999", headers=lab.analyst)
    assert response.json()["error"]["code"] == "SAMPLE_NOT_FOUND"


# --- Cenários negativos complementares (ETAPA 12) -------------------------------


def _registration(lab: Lab, **overrides: object) -> dict[str, object]:
    return {
        "product_id": lab.product_id,
        "client_id": lab.client_id,
        "lot_number": "L1",
        "origin": "PRODUCTION",
        "received_at": datetime.now(UTC).isoformat(),
        **overrides,
    }


@pytest.mark.rules("RN-02")
def test_inactive_client_cannot_send_samples(lab: Lab) -> None:
    response = lab.client.patch(
        f"{API}/clients/{lab.client_id}", json={"is_active": False}, headers=lab.admin
    )
    assert response.status_code == 200, response.text

    response = lab.post("/samples", lab.analyst, _registration(lab))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_CLIENT"


@pytest.mark.rules("RN-03")
def test_received_at_tolerates_small_clock_skew_only(lab: Lab) -> None:
    near = (datetime.now(UTC) + timedelta(minutes=2)).isoformat()
    response = lab.post("/samples", lab.analyst, _registration(lab, received_at=near))
    assert response.status_code == 201, response.text

    far = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    response = lab.post("/samples", lab.analyst, _registration(lab, received_at=far))
    assert response.json()["error"]["code"] == "RECEIVED_AT_IN_FUTURE"


@pytest.mark.rules("RN-05")
def test_only_existing_active_tests_can_be_assigned(lab: Lab) -> None:
    response = lab.client.patch(
        f"{API}/test-definitions/{lab.tests['MOISTURE']}",
        json={"is_active": False},
        headers=lab.admin,
    )
    assert response.status_code == 200, response.text
    sample = lab.create_sample()

    response = lab.post(
        f"/samples/{sample['id']}/tests",
        lab.analyst,
        {"test_definition_ids": [lab.tests["MOISTURE"], 999]},
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_TEST_DEFINITION"
    assert sorted(error["details"]["test_definition_ids"]) == sorted([lab.tests["MOISTURE"], 999])
    assert {t["test_code"] for t in lab.get_sample(sample["id"])["tests"]} == {"PH", "DENSITY"}


@pytest.mark.rules("RN-07")
def test_completed_test_cannot_be_cancelled(lab: Lab, db: Session) -> None:
    sample = lab.create_sample()
    lab.analyze(sample, {"PH": "6.8"})
    test_id = lab.test_id(sample, "PH")

    response = lab.post(f"/sample-tests/{test_id}/cancel", lab.analyst, {"reason": "Engano"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SAMPLE_TEST_NOT_PENDING"
    assert "TEST_CANCELLED" not in _audit_actions(db, sample["id"])

    unknown = lab.post("/sample-tests/999/cancel", lab.analyst, {"reason": "Não existe"})
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "SAMPLE_TEST_NOT_FOUND"


@pytest.mark.rules("RN-14")
@pytest.mark.parametrize("final", ["APPROVED", "REJECTED", "CANCELLED"])
def test_final_sample_accepts_no_change(lab: Lab, db: Session, final: str) -> None:
    sample = lab.create_sample()
    if final == "CANCELLED":
        response = _action(lab, sample["id"], "cancel", lab.manager, {"reason": "Duplicada"})
    else:
        lab.analyze(sample)
        lab.submit(sample)
        response = (
            _action(lab, sample["id"], "approve", lab.reviewer, {"password": "Senha@2026"})
            if final == "APPROVED"
            else _action(lab, sample["id"], "reject", lab.reviewer, {"reason": "Fora do padrão"})
        )
    assert response.status_code == 200, response.text
    current = response.json()
    assert current["status"] == final
    assert current["allowed_actions"] == []
    audit_before = _audit_actions(db, sample["id"])

    attempts = {
        "edit": lab.client.patch(
            f"{API}/samples/{sample['id']}",
            json={"version": current["version"], "notes": "ajuste"},
            headers=lab.analyst,
        ),
        "assign": lab.post(
            f"/samples/{sample['id']}/tests",
            lab.analyst,
            {"test_definition_ids": [lab.tests["MOISTURE"]]},
        ),
        "cancel-test": lab.post(
            f"/sample-tests/{lab.test_id(sample, 'PH')}/cancel",
            lab.analyst,
            {"reason": "Depois de finalizada"},
        ),
        "result": lab.enter(sample, "PH", "6.9", reason="Depois de finalizada"),
        "start": _action(lab, sample["id"], "start-analysis", lab.analyst),
        "cancel": _action(lab, sample["id"], "cancel", lab.manager, {"reason": "Tarde demais"}),
        "reject": _action(lab, sample["id"], "reject", lab.reviewer, {"reason": "Tarde demais"}),
    }
    for name, response in attempts.items():
        assert response.status_code == 409, (name, response.text)
    assert lab.get_sample(sample["id"])["status"] == final
    assert _audit_actions(db, sample["id"]) == audit_before
