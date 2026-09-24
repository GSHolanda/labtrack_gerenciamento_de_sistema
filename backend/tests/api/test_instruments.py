"""Instrumentos pelo contrato HTTP: gestão, chave de integração e RN-19 a RN-24."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_instrument_key
from app.models import AuditLog, Instrument, InstrumentResult, TestResult

from ..conftest import DEFAULT_PASSWORD
from .conftest import API, Lab

# A calibração é comparada com a data UTC do servidor, não com a data local.
TODAY = datetime.now(UTC).date()
TOMORROW = TODAY + timedelta(days=1)
NEXT_YEAR = TODAY + timedelta(days=365)
YESTERDAY = TODAY - timedelta(days=1)


def _create_instrument(lab: Lab, **overrides: Any) -> dict[str, Any]:
    payload = {
        "code": "PH-METER-01",
        "name": "pHmetro de bancada",
        "instrument_type": "PH_METER",
        "manufacturer": "Metrohm",
        "serial_number": "SN-0001",
        "location": "Sala 2",
        "calibration_due_date": NEXT_YEAR.isoformat(),
        **overrides,
    }
    response = lab.post("/instruments", lab.admin, payload)
    assert response.status_code == 201, response.text
    return response.json()


def _key(instrument: dict[str, Any]) -> dict[str, str]:
    return {"X-Instrument-Key": instrument["api_key"]}


def _payload(sample: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    return {
        "instrument_id": "PH-METER-01",
        "sample_code": sample["sample_code"],
        "test": "PH",
        "result": 6.42,
        "unit": "pH",
        **overrides,
    }


def _send(lab: Lab, instrument: dict[str, Any], payload: Any) -> Any:
    return lab.client.post(f"{API}/instruments/results", headers=_key(instrument), json=payload)


def _started_sample(lab: Lab, **overrides: Any) -> dict[str, Any]:
    sample = lab.create_sample(**overrides)
    response = lab.post(f"/samples/{sample['id']}/start-analysis", lab.analyst)
    assert response.status_code == 200, response.text
    return response.json()


def _messages(db: Session) -> list[InstrumentResult]:
    db.expire_all()
    return list(db.scalars(select(InstrumentResult).order_by(InstrumentResult.id)))


def _results(db: Session) -> list[TestResult]:
    db.expire_all()
    return list(db.scalars(select(TestResult).order_by(TestResult.id)))


def _audit(db: Session, action: str) -> list[AuditLog]:
    db.expire_all()
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)))


# --- Gestão -------------------------------------------------------------------


def test_create_shows_key_once_and_stores_only_its_hash(lab: Lab, db: Session) -> None:
    created = _create_instrument(lab, code="ph-meter-01")

    assert created["code"] == "PH-METER-01"
    assert created["api_key"].startswith("lt_inst_")
    assert created["status"] == "ACTIVE"
    assert created["calibration_valid"] is True
    assert created["online"] is False
    assert created["last_communication_at"] is None

    detail = lab.client.get(f"{API}/instruments/{created['id']}", headers=lab.analyst)
    assert detail.status_code == 200
    assert "api_key" not in detail.json()
    assert "api_key_hash" not in detail.json()

    stored = db.get(Instrument, created["id"])
    assert stored is not None
    assert stored.api_key_hash == hash_instrument_key(created["api_key"])
    assert created["api_key"] not in stored.api_key_hash

    event = _audit(db, "INSTRUMENT_CREATED")[-1]
    assert event.actor_name == "Administrador do Sistema"
    assert event.entity_label == "PH-METER-01"
    assert event.new_value["calibration_due_date"] == NEXT_YEAR.isoformat()
    assert created["api_key"] not in str(event.new_value)
    assert stored.api_key_hash not in str(event.new_value)


def test_every_instrument_gets_its_own_key(lab: Lab) -> None:
    first = _create_instrument(lab)
    second = _create_instrument(lab, code="PH-METER-02", serial_number="SN-0002")
    assert first["api_key"] != second["api_key"]


@pytest.mark.parametrize("role", ["analyst", "reviewer", "manager"])
def test_only_admin_manages_instruments(lab: Lab, role: str) -> None:
    instrument = _create_instrument(lab)
    headers = getattr(lab, role)
    attempts = [
        lab.post("/instruments", headers, {"code": "X-01"}),
        lab.client.patch(
            f"{API}/instruments/{instrument['id']}", headers=headers, json={"location": "Sala 9"}
        ),
        lab.post(f"/instruments/{instrument['id']}/rotate-key", headers),
    ]
    for response in attempts:
        assert response.status_code == 403
        assert response.json()["error"]["details"]["required_permission"] == "INSTRUMENT_MANAGE"


@pytest.mark.parametrize("role", ["admin", "analyst", "reviewer", "manager"])
def test_every_profile_reads_instruments_and_messages(lab: Lab, role: str) -> None:
    instrument = _create_instrument(lab)
    headers = getattr(lab, role)
    for path in ("/instruments", f"/instruments/{instrument['id']}"):
        assert lab.client.get(f"{API}{path}", headers=headers).status_code == 200
    messages = lab.client.get(f"{API}/instruments/{instrument['id']}/messages", headers=headers)
    assert messages.status_code == 200


def test_management_requires_user_authentication(lab: Lab) -> None:
    instrument = _create_instrument(lab)
    assert lab.client.get(f"{API}/instruments").status_code == 401
    # A chave de um equipamento não substitui o login de um usuário.
    response = lab.client.get(f"{API}/instruments", headers=_key(instrument))
    assert response.status_code == 401


def test_duplicated_code_or_serial_is_refused(lab: Lab) -> None:
    _create_instrument(lab)
    for overrides in ({"code": "ph-meter-01", "serial_number": "SN-9"}, {"code": "PH-METER-09"}):
        payload = {
            "name": "Outro",
            "instrument_type": "PH_METER",
            "calibration_due_date": NEXT_YEAR.isoformat(),
            "serial_number": "SN-0001",
            **overrides,
        }
        response = lab.post("/instruments", lab.admin, payload)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "DUPLICATED_INSTRUMENT"


@pytest.mark.parametrize(
    "payload",
    [
        {"code": "PH-METER-02"},
        {"instrument_type": "HPLC"},
        {"name": None},
        {"status": None},
        {"calibration_due_date": None},
        {"status": "BROKEN"},
    ],
)
def test_update_refuses_identity_changes_and_nulls(lab: Lab, payload: dict[str, Any]) -> None:
    instrument = _create_instrument(lab)
    response = lab.client.patch(
        f"{API}/instruments/{instrument['id']}", headers=lab.admin, json=payload
    )
    assert response.status_code == 422


def test_update_audits_only_changed_fields(lab: Lab, db: Session) -> None:
    instrument = _create_instrument(lab)
    response = lab.client.patch(
        f"{API}/instruments/{instrument['id']}",
        headers=lab.admin,
        json={
            "location": "Sala 3",
            "status": "MAINTENANCE",
            "calibration_due_date": TOMORROW.isoformat(),
            "manufacturer": "Metrohm",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["location"], body["status"]) == ("Sala 3", "MAINTENANCE")
    event = _audit(db, "INSTRUMENT_UPDATED")[-1]
    assert event.old_value == {
        "location": "Sala 2",
        "status": "ACTIVE",
        "calibration_due_date": NEXT_YEAR.isoformat(),
    }
    assert event.new_value == {
        "location": "Sala 3",
        "status": "MAINTENANCE",
        "calibration_due_date": TOMORROW.isoformat(),
    }

    unchanged = lab.client.patch(
        f"{API}/instruments/{instrument['id']}", headers=lab.admin, json={"location": "Sala 3"}
    )
    assert unchanged.status_code == 200
    assert len(_audit(db, "INSTRUMENT_UPDATED")) == 1


def test_rotation_invalidates_the_previous_key(lab: Lab, db: Session) -> None:
    instrument = _create_instrument(lab)
    rotated = lab.post(
        f"/instruments/{instrument['id']}/rotate-key",
        lab.admin,
        {"reason": "Chave exposta no log do equipamento"},
    )
    assert rotated.status_code == 200, rotated.text
    new_key = rotated.json()["api_key"]
    assert new_key != instrument["api_key"]

    old = lab.client.post(f"{API}/instruments/heartbeat", headers=_key(instrument))
    assert old.status_code == 401
    assert old.json()["error"]["code"] == "INVALID_INSTRUMENT_KEY"
    new = lab.client.post(f"{API}/instruments/heartbeat", headers={"X-Instrument-Key": new_key})
    assert new.status_code == 200

    event = _audit(db, "INSTRUMENT_KEY_ROTATED")[-1]
    assert event.reason == "Chave exposta no log do equipamento"
    assert event.old_value is None
    assert event.new_value is None


def test_rotation_reason_is_optional(lab: Lab) -> None:
    instrument = _create_instrument(lab)
    assert lab.post(f"/instruments/{instrument['id']}/rotate-key", lab.admin).status_code == 200


def test_unknown_instrument_returns_404(lab: Lab) -> None:
    for response in (
        lab.client.get(f"{API}/instruments/999", headers=lab.admin),
        lab.client.get(f"{API}/instruments/999/messages", headers=lab.admin),
        lab.client.patch(f"{API}/instruments/999", headers=lab.admin, json={"location": "X"}),
        lab.post("/instruments/999/rotate-key", lab.admin),
    ):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "INSTRUMENT_NOT_FOUND"


def test_list_filters_instruments(lab: Lab) -> None:
    _create_instrument(lab)
    _create_instrument(
        lab,
        code="KF-01",
        name="Karl Fischer",
        instrument_type="MOISTURE_ANALYZER",
        serial_number="SN-0002",
        status="MAINTENANCE",
    )

    def codes(**params: Any) -> list[str]:
        response = lab.client.get(f"{API}/instruments", headers=lab.analyst, params=params)
        assert response.status_code == 200, response.text
        return [item["code"] for item in response.json()["items"]]

    assert codes() == ["KF-01", "PH-METER-01"]
    assert codes(status="MAINTENANCE") == ["KF-01"]
    assert codes(instrument_type="PH_METER") == ["PH-METER-01"]
    assert codes(q="fischer") == ["KF-01"]
    assert codes(sort="-code") == ["PH-METER-01", "KF-01"]


# --- Autenticação da integração ------------------------------------------------


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Instrument-Key": "lt_inst_invalida"}, {"X-Instrument-Key": "x" * 500}],
    ids=["missing", "unknown", "too-long"],
)
@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/worklist"), ("POST", "/results"), ("POST", "/heartbeat")],
)
def test_integration_requires_a_valid_key(
    lab: Lab, db: Session, headers: dict[str, str], method: str, path: str
) -> None:
    _create_instrument(lab)
    response = lab.client.request(method, f"{API}/instruments{path}", headers=headers, json={})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_INSTRUMENT_KEY"
    assert _messages(db) == []


def test_user_token_does_not_authenticate_an_instrument(lab: Lab) -> None:
    response = lab.client.get(f"{API}/instruments/worklist", headers=lab.analyst)
    assert response.status_code == 401


# --- Worklist e heartbeat -------------------------------------------------------


def test_worklist_lists_pending_compatible_tests_by_priority(lab: Lab) -> None:
    instrument = _create_instrument(lab)
    normal = _started_sample(lab, priority="NORMAL")
    urgent = _started_sample(lab, priority="URGENT")
    lab.create_sample(priority="URGENT")  # ainda RECEIVED: fora da worklist
    done = _started_sample(lab, priority="URGENT")
    assert lab.enter(done, "PH", "6.8").status_code == 201

    response = lab.client.get(f"{API}/instruments/worklist", headers=_key(instrument))

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["instrument_id"], body["instrument_type"]) == ("PH-METER-01", "PH_METER")
    items = body["items"]
    assert [item["sample_code"] for item in items] == [urgent["sample_code"], normal["sample_code"]]
    assert {item["test"] for item in items} == {"PH"}  # densidade é de outro equipamento
    first = items[0]
    assert first["priority"] == "URGENT"
    assert first["unit"] == "pH"
    assert (Decimal(first["spec_min"]), Decimal(first["spec_max"])) == (Decimal("5.5"), Decimal(7))
    assert first["decimal_places"] == 2

    limited = lab.client.get(
        f"{API}/instruments/worklist", headers=_key(instrument), params={"limit": 1}
    )
    assert [item["sample_code"] for item in limited.json()["items"]] == [urgent["sample_code"]]


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"status": "MAINTENANCE"}, "INSTRUMENT_NOT_ACTIVE"),
        ({"status": "INACTIVE"}, "INSTRUMENT_NOT_ACTIVE"),
        ({"calibration_due_date": YESTERDAY.isoformat()}, "CALIBRATION_EXPIRED"),
    ],
)
def test_worklist_refused_when_instrument_cannot_measure(
    lab: Lab, overrides: dict[str, Any], code: str
) -> None:
    instrument = _create_instrument(lab, **overrides)
    _started_sample(lab)

    response = lab.client.get(f"{API}/instruments/worklist", headers=_key(instrument))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == code
    detail = lab.client.get(f"{API}/instruments/{instrument['id']}", headers=lab.admin).json()
    assert detail["online"] is True  # a comunicação foi registrada mesmo assim


def test_calibration_is_valid_until_the_due_date(lab: Lab) -> None:
    instrument = _create_instrument(lab, calibration_due_date=TODAY.isoformat())
    assert instrument["calibration_valid"] is True
    response = lab.client.get(f"{API}/instruments/worklist", headers=_key(instrument))
    assert response.status_code == 200


def test_heartbeat_marks_instrument_online(lab: Lab) -> None:
    instrument = _create_instrument(lab, status="MAINTENANCE")
    before = datetime.now(UTC)

    response = lab.client.post(
        f"{API}/instruments/heartbeat",
        headers=_key(instrument),
        json={"instrument_id": "ph-meter-01"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["instrument_id"] == "PH-METER-01"
    assert body["status"] == "MAINTENANCE"
    assert body["calibration_valid"] is True
    assert body["can_measure"] is False
    detail = lab.client.get(f"{API}/instruments/{instrument['id']}", headers=lab.analyst).json()
    assert detail["online"] is True
    assert datetime.fromisoformat(detail["last_communication_at"]) >= before


def test_heartbeat_body_is_optional_but_must_match_the_key(lab: Lab) -> None:
    instrument = _create_instrument(lab)
    assert (
        lab.client.post(f"{API}/instruments/heartbeat", headers=_key(instrument)).status_code == 200
    )
    response = lab.client.post(
        f"{API}/instruments/heartbeat",
        headers=_key(instrument),
        json={"instrument_id": "PH-METER-02"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSTRUMENT_ID_MISMATCH"


# --- Resultados aceitos ---------------------------------------------------------


@pytest.mark.parametrize(("value", "expected"), [("6.42", "IN_SPEC"), ("7.01", "OOS")])
def test_accepted_result_is_recorded_logged_and_audited(
    lab: Lab, db: Session, value: str, expected: str
) -> None:
    instrument = _create_instrument(lab)
    sample = _started_sample(lab)

    response = _send(lab, instrument, _payload(sample, result=value, test="ph"))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "ACCEPTED"
    assert body["sample_code"] == sample["sample_code"]
    assert body["test"] == "PH"
    assert Decimal(body["result"]) == Decimal(value)
    assert isinstance(body["result"], str)
    assert body["spec_status"] == expected
    assert (Decimal(body["spec_min"]), Decimal(body["spec_max"])) == (Decimal("5.5"), Decimal(7))

    ph = next(t for t in lab.get_sample(sample["id"])["tests"] if t["test_code"] == "PH")
    assert ph["status"] == "COMPLETED"
    current = ph["current_result"]
    assert current["id"] == body["result_id"]
    assert current["source"] == "INSTRUMENT"
    assert current["instrument_code"] == "PH-METER-01"
    assert current["entered_by"] is None
    assert ph["had_oos"] is (expected == "OOS")

    [message] = _messages(db)
    assert message.id == body["message_id"]
    assert message.status == "ACCEPTED"
    assert message.test_result_id == body["result_id"]
    assert (message.sample_code, message.test_code, message.unit) == (
        sample["sample_code"],
        "PH",
        "pH",
    )
    assert message.value == Decimal(value)
    assert message.payload["test"] == "ph"  # mensagem guardada como recebida

    event = _audit(db, "RESULT_ENTERED")[-1]
    assert event.actor_type == "INSTRUMENT"
    assert event.actor_name == "PH-METER-01"
    assert event.instrument_id == instrument["id"]
    assert event.user_id is None
    assert event.sample_id == sample["id"]
    assert event.new_value["source"] == "INSTRUMENT"
    assert event.new_value["spec_status"] == expected

    timeline = lab.client.get(f"{API}/samples/{sample['id']}/timeline", headers=lab.analyst).json()[
        "items"
    ]
    assert timeline[-1]["actor_name"] == "PH-METER-01"
    assert timeline[-1]["has_oos"] is (expected == "OOS")


def test_duplicate_submission_never_overwrites_the_result(lab: Lab, db: Session) -> None:
    instrument = _create_instrument(lab)
    sample = _started_sample(lab)
    first = _send(lab, instrument, _payload(sample, result="6.4"))
    assert first.status_code == 201

    second = _send(lab, instrument, _payload(sample, result="6.9"))

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "TEST_ALREADY_COMPLETED"
    [result] = _results(db)
    assert (result.value, result.version, result.is_current) == (Decimal("6.4"), 1, True)
    assert [m.status for m in _messages(db)] == ["ACCEPTED", "REJECTED"]


def test_correction_of_instrument_result_is_manual_and_justified(lab: Lab, db: Session) -> None:
    instrument = _create_instrument(lab)
    sample = _started_sample(lab)
    assert _send(lab, instrument, _payload(sample, result="7.3")).status_code == 201

    amended = lab.enter(sample, "PH", "6.9", reason="Eletrodo sem calibração no dia")

    assert amended.status_code == 201, amended.text
    body = amended.json()
    assert (body["version"], body["source"]) == (2, "MANUAL")
    assert body["entered_by"]["full_name"] == "Carlos Silva"
    versions = lab.client.get(
        f"{API}/sample-tests/{lab.test_id(sample, 'PH')}/results", headers=lab.analyst
    ).json()
    assert [(v["source"], v["is_current"]) for v in versions] == [
        ("INSTRUMENT", False),
        ("MANUAL", True),
    ]
    event = _audit(db, "RESULT_AMENDED")[-1]
    assert event.old_value["spec_status"] == "OOS"
    assert event.reason == "Eletrodo sem calibração no dia"


def test_instrument_results_complete_the_review_flow(lab: Lab) -> None:
    ph_meter = _create_instrument(lab)
    density_meter = _create_instrument(
        lab, code="DENS-01", instrument_type="DENSITY_METER", serial_number="SN-0002"
    )
    sample = _started_sample(lab)
    assert _send(lab, ph_meter, _payload(sample)).status_code == 201
    density = _payload(sample, instrument_id="DENS-01", test="DENSITY", result="1.021", unit="g/mL")
    assert _send(lab, density_meter, density).status_code == 201
    lab.submit(sample)

    # Nenhum resultado foi lançado por usuário: a revisora aprova normalmente.
    approved = lab.post(
        f"/samples/{sample['id']}/approve", lab.reviewer, {"password": DEFAULT_PASSWORD}
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"


# --- Resultados recusados (RN-19 a RN-24) --------------------------------------

Setup = Callable[[Lab], tuple[dict[str, Any], Any, int | None]]


def _mismatch(lab: Lab) -> tuple[dict[str, Any], Any, int | None]:
    sample = _started_sample(lab)
    _create_instrument(lab, code="PH-METER-02", serial_number="SN-0002")
    return _create_instrument(lab), _payload(sample, instrument_id="PH-METER-02"), sample["id"]


def _not_active(lab: Lab) -> tuple[dict[str, Any], Any, int | None]:
    sample = _started_sample(lab)
    return _create_instrument(lab, status="MAINTENANCE"), _payload(sample), sample["id"]


def _calibration(lab: Lab) -> tuple[dict[str, Any], Any, int | None]:
    sample = _started_sample(lab)
    instrument = _create_instrument(lab, calibration_due_date=YESTERDAY.isoformat())
    return instrument, _payload(sample), sample["id"]


def _unknown_sample(lab: Lab) -> tuple[dict[str, Any], Any, int | None]:
    return _create_instrument(lab), _payload({"sample_code": "SMP-2026-9999"}), None


def _received(lab: Lab) -> tuple[dict[str, Any], Any, int | None]:
    sample = lab.create_sample()
    return _create_instrument(lab), _payload(sample), sample["id"]


def _not_assigned(lab: Lab) -> tuple[dict[str, Any], Any, int | None]:
    sample = _started_sample(lab)
    instrument = _create_instrument(lab)
    return instrument, _payload(sample, test="MOISTURE", unit="%"), sample["id"]


def _cancelled_test(lab: Lab) -> tuple[dict[str, Any], Any, int | None]:
    sample = lab.create_sample()
    cancelled = lab.post(
        f"/sample-tests/{lab.test_id(sample, 'PH')}/cancel",
        lab.analyst,
        {"reason": "Teste solicitado por engano"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert lab.post(f"/samples/{sample['id']}/start-analysis", lab.analyst).status_code == 200
    return _create_instrument(lab), _payload(sample), sample["id"]


def _wrong_type(lab: Lab) -> tuple[dict[str, Any], Any, int | None]:
    sample = _started_sample(lab)
    instrument = _create_instrument(lab)
    return instrument, _payload(sample, test="DENSITY", unit="g/mL", result="1.02"), sample["id"]


def _completed(lab: Lab) -> tuple[dict[str, Any], Any, int | None]:
    sample = _started_sample(lab)
    assert lab.enter(sample, "PH", "6.8").status_code == 201
    return _create_instrument(lab), _payload(sample), sample["id"]


def _wrong_unit(lab: Lab) -> tuple[dict[str, Any], Any, int | None]:
    sample = _started_sample(lab)
    return _create_instrument(lab), _payload(sample, unit="ph"), sample["id"]


REJECTIONS: list[tuple[str, Setup, int, str]] = [
    ("id-mismatch", _mismatch, 403, "INSTRUMENT_ID_MISMATCH"),
    ("not-active", _not_active, 409, "INSTRUMENT_NOT_ACTIVE"),
    ("calibration", _calibration, 409, "CALIBRATION_EXPIRED"),
    ("unknown-sample", _unknown_sample, 404, "SAMPLE_NOT_FOUND"),
    ("received-sample", _received, 409, "SAMPLE_NOT_IN_ANALYSIS"),
    ("not-assigned", _not_assigned, 409, "TEST_NOT_ASSIGNED"),
    ("cancelled-test", _cancelled_test, 409, "SAMPLE_TEST_CANCELLED"),
    ("wrong-type", _wrong_type, 409, "INSTRUMENT_TYPE_MISMATCH"),
    ("completed", _completed, 409, "TEST_ALREADY_COMPLETED"),
    ("wrong-unit", _wrong_unit, 422, "UNIT_MISMATCH"),
]


@pytest.mark.parametrize(
    ("setup", "status_code", "code"),
    [row[1:] for row in REJECTIONS],
    ids=[row[0] for row in REJECTIONS],
)
def test_rejected_message_is_logged_and_audited_without_result(
    lab: Lab, db: Session, setup: Setup, status_code: int, code: str
) -> None:
    instrument, payload, sample_id = setup(lab)
    results_before = [(r.id, r.value, r.is_current) for r in _results(db)]

    response = _send(lab, instrument, payload)

    assert response.status_code == status_code, response.text
    error = response.json()["error"]
    assert error["code"] == code
    assert [(r.id, r.value, r.is_current) for r in _results(db)] == results_before

    message = _messages(db)[-1]
    assert error["details"]["message_id"] == message.id
    assert message.instrument_id == instrument["id"]
    assert message.status == "REJECTED"
    assert message.error_code == code
    assert message.error_message == error["message"]
    assert message.test_result_id is None
    assert message.payload == payload
    assert message.sample_code == payload["sample_code"]
    assert message.value == Decimal(str(payload["result"]))

    event = _audit(db, "INSTRUMENT_MESSAGE_REJECTED")[-1]
    assert event.actor_type == "INSTRUMENT"
    assert event.actor_name == "PH-METER-01"
    assert event.entity_id == str(message.id)
    assert event.sample_id == sample_id
    assert event.new_value["error_code"] == code
    assert event.reason == error["message"]

    detail = lab.client.get(f"{API}/instruments/{instrument['id']}", headers=lab.admin).json()
    assert detail["online"] is True


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        "7.2",
        {"instrument_id": "PH-METER-01", "sample_code": "SMP-2026-0001", "test": "PH"},
        {
            "instrument_id": "PH-METER-01",
            "sample_code": "SMP-2026-0001",
            "test": "PH",
            "result": "sete",
            "unit": "pH",
        },
        {
            "instrument_id": "PH-METER-01",
            "sample_code": "SMP-2026-0001",
            "test": "PH",
            "result": "7.123456",
            "unit": "pH",
        },
        {
            "instrument_id": "PH-METER-01",
            "sample_code": "SMP-2026-0001",
            "test": "PH",
            "result": 7.2,
            "unit": "pH",
            "operator": "carlos",
        },
    ],
    ids=["empty", "list", "string", "missing-result", "text", "precision", "extra-field"],
)
def test_malformed_message_is_logged(lab: Lab, db: Session, payload: Any) -> None:
    instrument = _create_instrument(lab)
    kwargs = {} if payload is None else {"json": payload}

    response = lab.client.post(f"{API}/instruments/results", headers=_key(instrument), **kwargs)

    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "INVALID_PAYLOAD"
    assert error["details"]["errors"]
    [message] = _messages(db)
    assert message.status == "REJECTED"
    assert message.error_code == "INVALID_PAYLOAD"
    assert message.payload == payload
    assert message.value is None
    if isinstance(payload, dict):
        assert message.sample_code == "SMP-2026-0001"
        assert message.test_code == "PH"
    assert _audit(db, "INSTRUMENT_MESSAGE_REJECTED")[-1].sample_id is None
    assert _results(db) == []


def test_rejection_appears_in_sample_timeline(lab: Lab) -> None:
    instrument = _create_instrument(lab)
    sample = lab.create_sample()
    assert _send(lab, instrument, _payload(sample)).status_code == 409

    events = lab.client.get(f"{API}/samples/{sample['id']}/timeline", headers=lab.analyst).json()[
        "items"
    ]

    rejection = events[-1]
    assert rejection["action"] == "INSTRUMENT_MESSAGE_REJECTED"
    assert rejection["actor_type"] == "INSTRUMENT"
    assert rejection["new_value"]["error_code"] == "SAMPLE_NOT_IN_ANALYSIS"
    assert rejection["has_oos"] is False


def test_message_log_filters_by_status(lab: Lab) -> None:
    instrument = _create_instrument(lab)
    other = _create_instrument(
        lab, code="DENS-01", instrument_type="DENSITY_METER", serial_number="SN-0002"
    )
    sample = _started_sample(lab)
    assert _send(lab, instrument, _payload(sample, unit="mV")).status_code == 422
    assert _send(lab, instrument, _payload(sample)).status_code == 201

    def messages(instrument_id: int, **params: Any) -> list[dict[str, Any]]:
        response = lab.client.get(
            f"{API}/instruments/{instrument_id}/messages", headers=lab.reviewer, params=params
        )
        assert response.status_code == 200, response.text
        return response.json()["items"]

    everything = messages(instrument["id"])
    assert [m["status"] for m in everything] == ["ACCEPTED", "REJECTED"]  # mais recentes antes
    rejected = messages(instrument["id"], status="REJECTED")
    assert len(rejected) == 1
    assert rejected[0]["error_code"] == "UNIT_MISMATCH"
    assert rejected[0]["payload"]["unit"] == "mV"
    assert messages(instrument["id"], status="ACCEPTED")[0]["test_result_id"] is not None
    assert messages(other["id"]) == []


def test_audit_trail_stays_verifiable_and_filterable_by_instrument(lab: Lab) -> None:
    instrument = _create_instrument(lab)
    sample = _started_sample(lab)
    assert _send(lab, instrument, _payload(sample, unit="mV")).status_code == 422
    assert _send(lab, instrument, _payload(sample)).status_code == 201

    verification = lab.client.get(f"{API}/audit-logs/verify", headers=lab.reviewer).json()
    assert verification["valid"] is True
    events = lab.client.get(
        f"{API}/audit-logs",
        headers=lab.reviewer,
        params={"actor_type": "INSTRUMENT", "instrument_id": instrument["id"], "sort": "id"},
    ).json()["items"]
    assert [e["action"] for e in events] == ["INSTRUMENT_MESSAGE_REJECTED", "RESULT_ENTERED"]
