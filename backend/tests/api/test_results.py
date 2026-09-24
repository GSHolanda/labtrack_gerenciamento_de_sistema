"""Resultados e revisão pelo contrato HTTP: RN-09 a RN-18."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog

from ..conftest import DEFAULT_PASSWORD
from .conftest import API, Lab


def _history(lab: Lab, sample: dict[str, Any], code: str = "PH") -> list[dict[str, Any]]:
    response = lab.client.get(
        f"{API}/sample-tests/{lab.test_id(sample, code)}/results", headers=lab.reviewer
    )
    assert response.status_code == 200, response.text
    return response.json()


def _audit(db: Session, sample_id: int) -> list[AuditLog]:
    db.expire_all()
    return list(
        db.scalars(select(AuditLog).where(AuditLog.sample_id == sample_id).order_by(AuditLog.id))
    )


def _assert_same_result(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    # SQLite não preserva o fuso e NUMERIC retorna quatro casas ao reler do banco.
    def normalized(result: dict[str, Any]) -> dict[str, Any]:
        entered_at = datetime.fromisoformat(result["entered_at"])
        if entered_at.tzinfo is None:
            entered_at = entered_at.replace(tzinfo=UTC)
        return {**result, "value": Decimal(result["value"]), "entered_at": entered_at}

    assert normalized(actual) == normalized(expected)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("5.4999", "OOS"),
        ("5.5", "IN_SPEC"),
        ("6.8", "IN_SPEC"),
        ("7.0", "IN_SPEC"),
        ("7.0001", "OOS"),
    ],
)
def test_result_uses_product_limits_and_is_audited(
    lab: Lab, db: Session, value: str, expected: str
) -> None:
    sample = lab.create_sample()
    started = lab.post(f"/samples/{sample['id']}/start-analysis", lab.analyst)
    assert started.status_code == 200

    response = lab.enter(sample, "PH", value)

    assert response.status_code == 201, response.text
    result = response.json()
    assert isinstance(result["value"], str)
    assert Decimal(result["value"]) == Decimal(value)
    assert result["spec_status"] == expected
    assert result["unit"] == "pH"
    assert result["source"] == "MANUAL"
    assert result["entered_by"]["full_name"] == "Carlos Silva"
    assert result["instrument_code"] is None
    assert result["entered_at"] is not None
    assert result["version"] == 1
    assert result["is_current"] is True

    detail = lab.get_sample(sample["id"])
    ph = next(t for t in detail["tests"] if t["test_code"] == "PH")
    assert ph["status"] == "COMPLETED"
    _assert_same_result(ph["current_result"], result)
    assert ph["result_versions"] == 1
    assert ph["had_oos"] is (expected == "OOS")
    assert detail["oos_tests"] == (["PH"] if expected == "OOS" else [])
    event = _audit(db, sample["id"])[-1]
    assert event.action == "RESULT_ENTERED"
    assert event.entity_id == str(result["id"])
    assert event.actor_name == "Carlos Silva"
    assert event.old_value is None
    assert Decimal(event.new_value["value"]) == Decimal(value)
    assert event.new_value["spec_status"] == expected


def test_received_sample_does_not_accept_results(lab: Lab, db: Session) -> None:
    sample = lab.create_sample()
    before = [event.id for event in _audit(db, sample["id"])]

    response = lab.enter(sample, "PH", "6.8")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SAMPLE_NOT_IN_ANALYSIS"
    assert _history(lab, sample) == []
    assert [event.id for event in _audit(db, sample["id"])] == before


@pytest.mark.parametrize("reason", [None, "", "   ", "erro"])
def test_amendment_requires_meaningful_reason(lab: Lab, reason: str | None) -> None:
    sample = lab.create_sample()
    lab.analyze(sample)
    original = _history(lab, sample)

    response = lab.post(
        f"/sample-tests/{lab.test_id(sample, 'PH')}/results",
        lab.analyst,
        {"value": "6.9", "change_reason": reason},
    )

    assert response.status_code == 422
    if reason is None:
        assert response.json()["error"]["code"] == "CHANGE_REASON_REQUIRED"
    assert _history(lab, sample) == original


def test_correction_preserves_oos_history_and_audits_both_values(lab: Lab, db: Session) -> None:
    sample = lab.create_sample()
    lab.analyze(sample, {"PH": "8.1", "DENSITY": "1.02"})
    original = _history(lab, sample)[0]

    response = lab.enter(sample, "PH", "6.8", "Erro de transcrição")

    assert response.status_code == 201, response.text
    corrected = response.json()
    history = _history(lab, sample)
    assert len(history) == 2
    assert history[0] == {**original, "is_current": False}
    _assert_same_result(history[1], corrected)
    assert corrected["version"] == 2
    assert corrected["is_current"] is True
    assert corrected["spec_status"] == "IN_SPEC"
    assert corrected["change_reason"] == "Erro de transcrição"
    detail = lab.get_sample(sample["id"])
    ph = next(t for t in detail["tests"] if t["test_code"] == "PH")
    assert ph["had_oos"] is True
    assert ph["result_versions"] == 2
    _assert_same_result(ph["current_result"], corrected)
    assert detail["oos_tests"] == []
    event = _audit(db, sample["id"])[-1]
    assert event.action == "RESULT_AMENDED"
    assert event.reason == "Erro de transcrição"
    assert Decimal(event.old_value["value"]) == Decimal("8.1")
    assert event.old_value["spec_status"] == "OOS"
    assert Decimal(event.new_value["value"]) == Decimal("6.8")
    assert event.new_value["spec_status"] == "IN_SPEC"

    lab.submit(sample)
    approved = lab.post(
        f"/samples/{sample['id']}/approve", lab.reviewer, {"password": DEFAULT_PASSWORD}
    )
    assert approved.status_code == 200, approved.text
    assert next(t for t in approved.json()["tests"] if t["test_code"] == "PH")["had_oos"]


@pytest.mark.parametrize("value", ["6.12345", "10000000000", "NaN", "Infinity"])
def test_invalid_decimal_is_rejected_without_recording_result(lab: Lab, value: str) -> None:
    sample = lab.create_sample()
    assert lab.post(f"/samples/{sample['id']}/start-analysis", lab.analyst).status_code == 200

    response = lab.enter(sample, "PH", value)

    assert response.status_code == 422
    assert _history(lab, sample) == []


@pytest.mark.parametrize("role", ["reviewer", "admin", "manager"])
def test_only_analyst_can_enter_results(lab: Lab, role: str) -> None:
    sample = lab.create_sample()
    assert lab.post(f"/samples/{sample['id']}/start-analysis", lab.analyst).status_code == 200

    response = lab.post(
        f"/sample-tests/{lab.test_id(sample, 'PH')}/results",
        getattr(lab, role),
        {"value": "6.8"},
    )

    assert response.status_code == 403
    assert _history(lab, sample) == []


def test_cancelled_test_does_not_accept_results(lab: Lab) -> None:
    sample = lab.create_sample()
    cancelled = lab.post(
        f"/sample-tests/{lab.test_id(sample, 'PH')}/cancel",
        lab.analyst,
        {"reason": "Teste atribuído por engano"},
    )
    assert cancelled.status_code == 200
    assert lab.post(f"/samples/{sample['id']}/start-analysis", lab.analyst).status_code == 200

    response = lab.enter(sample, "PH", "6.8")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SAMPLE_TEST_CANCELLED"
    assert _history(lab, sample) == []


@pytest.mark.parametrize("state", ["AWAITING_REVIEW", "APPROVED", "REJECTED", "CANCELLED"])
def test_results_are_locked_after_submission(lab: Lab, state: str) -> None:
    sample = lab.create_sample()
    lab.analyze(sample)
    lab.submit(sample)
    if state != "AWAITING_REVIEW":
        action, headers, payload = {
            "APPROVED": ("approve", lab.reviewer, {"password": DEFAULT_PASSWORD}),
            "REJECTED": ("reject", lab.reviewer, {"reason": "Desvio no procedimento"}),
            "CANCELLED": ("cancel", lab.manager, {"reason": "Amostra duplicada"}),
        }[state]
        assert lab.post(f"/samples/{sample['id']}/{action}", headers, payload).status_code == 200
    original = _history(lab, sample)

    response = lab.enter(sample, "PH", "6.9", "Erro de transcrição")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SAMPLE_NOT_IN_ANALYSIS"
    assert lab.get_sample(sample["id"])["status"] == state
    assert _history(lab, sample) == original


def test_search_oos_defaults_to_current_results_and_can_include_history(lab: Lab) -> None:
    sample = lab.create_sample()
    lab.analyze(sample, {"PH": "8.1", "DENSITY": "1.02"})

    def search(**params: Any) -> dict[str, Any]:
        response = lab.client.get(f"{API}/results", params=params, headers=lab.reviewer)
        assert response.status_code == 200, response.text
        return response.json()

    oos = search(spec_status="OOS")
    assert oos["total"] == 1
    assert oos["items"][0]["test_code"] == "PH"
    assert oos["items"][0]["sample_code"] == sample["sample_code"]
    assert Decimal(oos["items"][0]["spec_max"]) == Decimal("7.0")
    assert lab.enter(sample, "PH", "6.8", "Erro de transcrição").status_code == 201
    assert search(spec_status="OOS")["total"] == 0
    historical = search(spec_status="OOS", current_only=False)
    assert historical["total"] == 1
    assert historical["items"][0]["is_current"] is False
    assert search()["total"] == 2
    assert search(current_only=False)["total"] == 3
    filtered = search(test_code="ph", sample_code=sample["sample_code"], source="MANUAL", size=1)
    assert filtered["total"] == 1
    assert filtered["items"][0]["version"] == 2
    assert search(source="INSTRUMENT")["total"] == 0


def test_approval_records_reviewer_timestamps_history_and_audit(lab: Lab, db: Session) -> None:
    sample = lab.create_sample()
    lab.analyze(sample)
    lab.submit(sample)

    response = lab.post(
        f"/samples/{sample['id']}/approve",
        lab.reviewer,
        {"password": DEFAULT_PASSWORD, "comment": "Resultados conferidos"},
    )

    assert response.status_code == 200, response.text
    approved = response.json()
    assert approved["status"] == "APPROVED"
    assert approved["reviewed_by"]["full_name"] == "Ana Souza"
    assert approved["reviewed_at"] is not None
    assert approved["completed_at"] == approved["reviewed_at"]
    assert approved["review_comment"] == "Resultados conferidos"
    assert approved["allowed_actions"] == []
    history = lab.client.get(
        f"{API}/samples/{sample['id']}/status-history", headers=lab.reviewer
    ).json()
    assert history[-1]["from_status"] == "AWAITING_REVIEW"
    assert history[-1]["to_status"] == "APPROVED"
    assert history[-1]["changed_by"] == approved["reviewed_by"]
    events = _audit(db, sample["id"])
    assert events[-1].action == "SAMPLE_STATUS_CHANGED"
    assert events[-1].new_value == {"status": "APPROVED"}
    assert DEFAULT_PASSWORD not in str([(e.old_value, e.new_value, e.reason) for e in events])


@pytest.mark.parametrize(
    ("value", "password", "status", "code"),
    [
        ("8.1", DEFAULT_PASSWORD, 409, "SAMPLE_HAS_OOS_RESULTS"),
        ("6.8", "Senha incorreta", 422, "INVALID_SIGNATURE"),
    ],
)
def test_failed_approval_does_not_change_sample_or_audit(
    lab: Lab, db: Session, value: str, password: str, status: int, code: str
) -> None:
    sample = lab.create_sample()
    lab.analyze(sample, {"PH": value, "DENSITY": "1.02"})
    lab.submit(sample)
    before = lab.get_sample(sample["id"])
    events_before = [event.id for event in _audit(db, sample["id"])]

    response = lab.post(f"/samples/{sample['id']}/approve", lab.reviewer, {"password": password})

    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    if code == "SAMPLE_HAS_OOS_RESULTS":
        assert response.json()["error"]["details"] == {"oos_tests": ["PH"]}
    assert lab.get_sample(sample["id"]) == before
    assert [event.id for event in _audit(db, sample["id"])] == events_before


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_result_author_cannot_review_after_role_change(lab: Lab, action: str) -> None:
    sample = lab.create_sample()
    lab.analyze(sample)
    lab.submit(sample)
    author_id = _history(lab, sample)[0]["entered_by"]["id"]
    changed = lab.client.patch(
        f"{API}/users/{author_id}", json={"role": "REVIEWER"}, headers=lab.admin
    )
    assert changed.status_code == 200, changed.text
    payload = {"password": DEFAULT_PASSWORD} if action == "approve" else {"reason": "Desvio"}

    response = lab.post(f"/samples/{sample['id']}/{action}", lab.analyst, payload)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FOUR_EYES_VIOLATION"
    assert lab.get_sample(sample["id"])["status"] == "AWAITING_REVIEW"


@pytest.mark.parametrize("action", ["reject", "return-to-analysis"])
@pytest.mark.parametrize("payload", [{}, {"reason": ""}, {"reason": "    "}])
def test_review_actions_require_reason(lab: Lab, action: str, payload: dict[str, str]) -> None:
    sample = lab.create_sample()
    lab.analyze(sample)
    lab.submit(sample)
    before = lab.get_sample(sample["id"])

    response = lab.post(f"/samples/{sample['id']}/{action}", lab.reviewer, payload)

    assert response.status_code == 422
    assert lab.get_sample(sample["id"]) == before


def test_rejection_records_reason_and_reviewer(lab: Lab, db: Session) -> None:
    sample = lab.create_sample()
    lab.analyze(sample, {"PH": "8.1", "DENSITY": "1.02"})
    lab.submit(sample)

    response = lab.post(
        f"/samples/{sample['id']}/reject", lab.reviewer, {"reason": "pH fora da especificação"}
    )

    assert response.status_code == 200, response.text
    rejected = response.json()
    assert rejected["status"] == "REJECTED"
    assert rejected["reviewed_by"]["full_name"] == "Ana Souza"
    assert rejected["reviewed_at"] is not None
    assert rejected["completed_at"] == rejected["reviewed_at"]
    assert rejected["review_comment"] == "pH fora da especificação"
    assert rejected["oos_tests"] == ["PH"]
    assert _audit(db, sample["id"])[-1].reason == "pH fora da especificação"


def test_return_to_analysis_allows_correction_and_resubmission(lab: Lab) -> None:
    sample = lab.create_sample()
    lab.analyze(sample, {"PH": "8.1", "DENSITY": "1.02"})
    lab.submit(sample)

    returned = lab.post(
        f"/samples/{sample['id']}/return-to-analysis",
        lab.reviewer,
        {"reason": "Conferir transcrição do pH"},
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["status"] == "IN_ANALYSIS"
    assert returned.json()["completed_at"] is None
    assert returned.json()["reviewed_by"] is None
    assert lab.enter(sample, "PH", "6.8", "Transcrição conferida").status_code == 201
    assert lab.submit(sample)["status"] == "AWAITING_REVIEW"
    approved = lab.post(
        f"/samples/{sample['id']}/approve", lab.reviewer, {"password": DEFAULT_PASSWORD}
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
    history = lab.client.get(
        f"{API}/samples/{sample['id']}/status-history", headers=lab.reviewer
    ).json()
    assert [entry["to_status"] for entry in history] == [
        "RECEIVED",
        "IN_ANALYSIS",
        "AWAITING_REVIEW",
        "IN_ANALYSIS",
        "AWAITING_REVIEW",
        "APPROVED",
    ]
    assert history[3]["reason"] == "Conferir transcrição do pH"


@pytest.mark.parametrize("action", ["approve", "reject", "return-to-analysis"])
@pytest.mark.parametrize("role", ["analyst", "admin", "manager"])
def test_only_reviewer_can_review(lab: Lab, action: str, role: str) -> None:
    sample = lab.create_sample()
    lab.analyze(sample)
    lab.submit(sample)
    payload = {"password": DEFAULT_PASSWORD} if action == "approve" else {"reason": "Reanalisar"}

    response = lab.post(f"/samples/{sample['id']}/{action}", getattr(lab, role), payload)

    assert response.status_code == 403
    assert lab.get_sample(sample["id"])["status"] == "AWAITING_REVIEW"
