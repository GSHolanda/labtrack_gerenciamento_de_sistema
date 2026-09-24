"""Audit trail e timeline: leitura autorizada, filtros e rastreabilidade."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.domain.audit import Actor, AuditAction
from app.models import AuditLog, Instrument
from app.services.audit_service import AuditService

from ..conftest import DEFAULT_PASSWORD
from .conftest import API, Lab


def _search(lab: Lab, **params: Any) -> dict[str, Any]:
    response = lab.client.get(f"{API}/audit-logs", headers=lab.reviewer, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _timeline(lab: Lab, sample_id: int, **params: Any) -> dict[str, Any]:
    response = lab.client.get(
        f"{API}/samples/{sample_id}/timeline", headers=lab.analyst, params=params
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("role", ["admin", "reviewer", "manager"])
@pytest.mark.parametrize("path", ["/audit-logs", "/audit-logs/verify"])
def test_audit_read_permission(lab: Lab, role: str, path: str) -> None:
    assert lab.client.get(f"{API}{path}", headers=getattr(lab, role)).status_code == 200


@pytest.mark.parametrize("path", ["/audit-logs", "/audit-logs/verify"])
def test_analyst_cannot_access_global_audit(lab: Lab, path: str) -> None:
    response = lab.client.get(f"{API}{path}", headers=lab.analyst)
    assert response.status_code == 403
    assert response.json()["error"]["details"]["required_permission"] == "AUDIT_READ"


@pytest.mark.parametrize("path", ["/audit-logs", "/audit-logs/verify", "/samples/1/timeline"])
def test_audit_endpoints_require_authentication(lab: Lab, path: str) -> None:
    assert lab.client.get(f"{API}{path}").status_code == 401


def test_search_combines_filters_and_preserves_actor_snapshot(lab: Lab) -> None:
    first = lab.create_sample()
    second = lab.create_sample()
    lab.analyze(first)
    events = _search(lab, sample_id=first["id"], action="RESULT_ENTERED")["items"]
    assert len(events) == 2
    event = events[0]
    filtered = _search(
        lab,
        sample_id=first["id"],
        action="RESULT_ENTERED",
        actor_type="USER",
        user_id=event["user_id"],
        entity_type="test_result",
        entity_id=event["entity_id"],
    )
    assert filtered["items"] == [event]
    assert filtered["total"] == 1
    assert _search(lab, sample_id=second["id"], action="RESULT_ENTERED")["total"] == 0
    assert _search(lab, sample_id=first["id"], user_id=999)["total"] == 0
    assert _search(lab, instrument_id=999)["total"] == 0
    assert _search(lab, actor_type="INSTRUMENT")["total"] == 0

    renamed = lab.client.patch(
        f"{API}/users/{event['user_id']}",
        headers=lab.admin,
        json={"full_name": "Carlos Silva Atualizado"},
    )
    assert renamed.status_code == 200
    persisted = _search(lab, entity_type="test_result", entity_id=event["entity_id"])["items"][0]
    assert persisted["actor_name"] == "Carlos Silva"
    assert persisted["request_id"]
    assert len(persisted["record_hash"]) == 64
    assert persisted["occurred_at"].endswith("Z")


def test_search_date_range_is_inclusive_and_normalizes_timezone(lab: Lab) -> None:
    sample = lab.create_sample()
    events = _search(lab, sample_id=sample["id"], sort="occurred_at")["items"]
    start, end = events[0]["occurred_at"], events[-1]["occurred_at"]
    assert _search(lab, sample_id=sample["id"], occurred_from=start, occurred_to=end)["total"] == 2
    assert (
        _search(lab, sample_id=sample["id"], occurred_from=start, occurred_to=start)["total"] == 1
    )
    # A mesma janela expressa em UTC-3 seleciona os mesmos registros.
    offset_start = start.removesuffix("Z")
    offset_start = (
        datetime.fromisoformat(offset_start) - timedelta(hours=3)
    ).isoformat() + "-03:00"
    assert (
        _search(lab, sample_id=sample["id"], occurred_from=offset_start, occurred_to=end)["total"]
        == 2
    )
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert _search(lab, occurred_from=tomorrow)["total"] == 0


def test_pagination_is_stable_with_equal_timestamps(lab: Lab, db: Session) -> None:
    sample = lab.create_sample()
    # Empate proposital no banco de teste SQLite; a API continua sem escrita.
    db.execute(
        update(AuditLog)
        .where(AuditLog.sample_id == sample["id"])
        .values(occurred_at=datetime(2026, 9, 23, tzinfo=UTC))
    )
    db.commit()
    first = _search(lab, sample_id=sample["id"], size=1, page=1)
    second = _search(lab, sample_id=sample["id"], size=1, page=2)
    assert first["total"] == second["total"] == 2
    assert first["pages"] == second["pages"] == 2
    assert first["items"][0]["id"] < second["items"][0]["id"]
    assert _search(lab, sample_id=sample["id"], size=1, page=3)["items"] == []
    timeline = _timeline(lab, sample["id"], size=1)
    assert timeline["items"][0]["id"] == first["items"][0]["id"]


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"size": 101},
        {"user_id": -1},
        {"sample_id": 0},
        {"action": "INVALID"},
        {"actor_type": "INVALID"},
        {"occurred_from": "invalid"},
        {"entity_id": "x" * 51},
    ],
)
def test_invalid_filters_return_standard_errors(lab: Lab, params: dict[str, Any]) -> None:
    response = lab.client.get(f"{API}/audit-logs", headers=lab.reviewer, params=params)
    assert response.status_code == 422
    assert response.json()["error"]["request_id"]


@pytest.mark.parametrize(
    ("params", "code"),
    [
        ({"sort": "record_hash"}, "INVALID_SORT_FIELD"),
        (
            {"occurred_from": "2026-09-24T00:00:00Z", "occurred_to": "2026-09-23T00:00:00"},
            "INVALID_DATE_RANGE",
        ),
    ],
)
def test_invalid_search_rules(lab: Lab, params: dict[str, str], code: str) -> None:
    response = lab.client.get(f"{API}/audit-logs", headers=lab.reviewer, params=params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


def test_verify_complete_chain_after_full_workflow_is_read_only(lab: Lab, db: Session) -> None:
    for _ in range(3):
        lab.create_sample()
    sample = lab.create_sample()
    lab.analyze(sample, {"PH": "8.1", "DENSITY": "1.02"})
    assert lab.enter(sample, "PH", "6.8", "Erro de transcrição").status_code == 201
    lab.submit(sample)
    assert (
        lab.post(
            f"/samples/{sample['id']}/approve", lab.reviewer, {"password": DEFAULT_PASSWORD}
        ).status_code
        == 200
    )
    count = db.scalar(select(func.count()).select_from(AuditLog))
    assert count > 20  # Verificação não fica limitada à primeira página da consulta.

    for _ in range(2):
        response = lab.client.get(f"{API}/audit-logs/verify", headers=lab.reviewer)
        assert response.status_code == 200, response.text
        assert response.json() == {
            "valid": True,
            "checked_records": count,
            "first_invalid_id": None,
            "error_code": None,
        }
    _search(lab)
    _timeline(lab, sample["id"])
    assert db.scalar(select(func.count()).select_from(AuditLog)) == count


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("reason", "Conteúdo adulterado", "RECORD_HASH_MISMATCH"),
        ("record_hash", "0" * 64, "RECORD_HASH_MISMATCH"),
        ("previous_hash", "0" * 64, "PREVIOUS_HASH_MISMATCH"),
    ],
)
def test_verify_reports_first_corrupted_record(
    lab: Lab, db: Session, field: str, value: str, code: str
) -> None:
    lab.create_sample()
    ids = list(db.scalars(select(AuditLog.id).order_by(AuditLog.id)))
    # Simula adulteração fora da aplicação. PostgreSQL bloqueia por trigger.
    db.execute(update(AuditLog).where(AuditLog.id == ids[2]).values({field: value}))
    db.commit()

    response = lab.client.get(f"{API}/audit-logs/verify", headers=lab.admin)

    assert response.status_code == 200
    assert response.json() == {
        "valid": False,
        "checked_records": 3,
        "first_invalid_id": ids[2],
        "error_code": code,
    }


def test_timeline_retains_oos_correction_and_workflow(lab: Lab) -> None:
    sample = lab.create_sample()
    unrelated = lab.create_sample()
    lab.analyze(sample, {"PH": "8.1", "DENSITY": "1.02"})
    assert lab.enter(sample, "PH", "6.8", "Erro de transcrição").status_code == 201
    lab.submit(sample)
    assert (
        lab.post(
            f"/samples/{sample['id']}/approve", lab.reviewer, {"password": DEFAULT_PASSWORD}
        ).status_code
        == 200
    )

    timeline = _timeline(lab, sample["id"])
    items = timeline["items"]
    assert [event["action"] for event in items] == [
        "SAMPLE_CREATED",
        "TESTS_ASSIGNED",
        "SAMPLE_STATUS_CHANGED",
        "RESULT_ENTERED",
        "RESULT_ENTERED",
        "RESULT_AMENDED",
        "SAMPLE_STATUS_CHANGED",
        "SAMPLE_STATUS_CHANGED",
    ]
    assert all(event["sample_id"] == sample["id"] for event in items)
    assert [(e["occurred_at"], e["id"]) for e in items] == sorted(
        (e["occurred_at"], e["id"]) for e in items
    )
    assert items[3]["has_oos"] is True
    assert items[3]["new_value"]["value"] == "8.1"
    assert items[4]["has_oos"] is False
    correction = items[5]
    assert correction["is_correction"] is True
    assert correction["has_oos"] is True
    assert correction["reason"] == "Erro de transcrição"
    assert correction["old_value"]["value"] == "8.1"
    assert correction["new_value"]["value"] == "6.8"
    assert items[-1]["actor_name"] == "Ana Souza"
    assert items[-1]["new_value"]["status"] == "APPROVED"
    assert all(
        not {"ip_address", "request_id", "record_hash", "previous_hash"} & e.keys() for e in items
    )
    assert _timeline(lab, unrelated["id"])["total"] == 2
    audit_ids = {e["id"] for e in _search(lab, sample_id=sample["id"])["items"]}
    assert audit_ids == {e["id"] for e in items}


@pytest.mark.parametrize("role", ["admin", "analyst", "reviewer", "manager"])
def test_all_sample_readers_can_access_timeline(lab: Lab, role: str) -> None:
    sample = lab.create_sample()
    response = lab.client.get(f"{API}/samples/{sample['id']}/timeline", headers=getattr(lab, role))
    assert response.status_code == 200


def test_timeline_unknown_sample(lab: Lab) -> None:
    response = lab.client.get(f"{API}/samples/999/timeline", headers=lab.analyst)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SAMPLE_NOT_FOUND"


def test_timeline_keeps_system_actor(lab: Lab, db: Session) -> None:
    sample = lab.create_sample()
    AuditService(db).record(
        Actor.system(),
        AuditAction.REPORT_GENERATED,
        entity_type="sample",
        entity_id=sample["id"],
        sample_id=sample["id"],
    )
    db.commit()
    event = _timeline(lab, sample["id"])["items"][-1]
    assert event["actor_type"] == "SYSTEM"
    assert event["actor_name"] == "LabTrack"
    assert event["user_id"] is None
    assert event["instrument_id"] is None


def test_instrument_actor_can_be_filtered_and_is_preserved_in_timeline(
    lab: Lab, db: Session
) -> None:
    sample = lab.create_sample()
    # A integração HTTP chega na ETAPA 8; aqui validamos o contrato de auditoria.
    instrument = Instrument(
        code="PH-METER-01",
        name="Medidor de pH",
        instrument_type="PH_METER",
        api_key_hash="test-only",
    )
    db.add(instrument)
    db.flush()
    entry = AuditService(db).record(
        Actor.instrument(instrument.id, instrument.code),
        AuditAction.INSTRUMENT_MESSAGE_REJECTED,
        entity_type="instrument",
        entity_id=instrument.id,
        sample_id=sample["id"],
        new_value={"error_code": "SAMPLE_NOT_IN_ANALYSIS"},
    )
    db.commit()

    filtered = _search(lab, instrument_id=instrument.id, actor_type="INSTRUMENT")
    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == entry.id
    event = _timeline(lab, sample["id"])["items"][-1]
    assert event["id"] == entry.id
    assert event["actor_name"] == "PH-METER-01"
    assert event["actor_type"] == "INSTRUMENT"
    assert event["instrument_id"] == instrument.id
    assert event["user_id"] is None


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_audit_has_no_write_endpoints(lab: Lab, method: str) -> None:
    for path in ("/audit-logs", "/audit-logs/1", "/audit-logs/verify"):
        response = lab.client.request(method, f"{API}{path}", headers=lab.admin)
        assert response.status_code in (404, 405)
