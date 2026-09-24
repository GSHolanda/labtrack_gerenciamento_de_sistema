"""Fluxo ponta a ponta pelo contrato HTTP, como o laboratório usa o sistema.

Um único cenário atravessa todas as áreas: cadastro do equipamento, registro da
amostra, análise com resultado enviado pelo instrumento, OOS, bloqueio da
aprovação, devolução, correção justificada, aprovação com senha, relatório,
timeline, audit trail e dashboard. Os testes de cada área verificam os detalhes;
este garante que as peças funcionam juntas, na ordem real.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from ..conftest import DEFAULT_PASSWORD
from .conftest import API, Lab

NEXT_YEAR = (datetime.now(UTC) + timedelta(days=365)).date().isoformat()


def _ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def _error(response: Any, status: int) -> str:
    assert response.status_code == status, response.text
    return response.json()["error"]["code"]


@pytest.mark.rules(
    "RN-01",
    "RN-04",
    "RN-06",
    "RN-08",
    "RN-10",
    "RN-11",
    "RN-12",
    "RN-13",
    "RN-14",
    "RN-15",
    "RN-16",
    "RN-17",
    "RN-18",
    "RN-22",
    "RN-24",
    "RN-27",
    "RN-28",
)
def test_sample_lifecycle_from_registration_to_report(lab: Lab) -> None:
    client = lab.client

    def get(path: str, headers: dict[str, str], **params: Any) -> Any:
        return _ok(client.get(f"{API}{path}", headers=headers, params=params))

    # 1. Administrador cadastra o pHmetro; a chave aparece uma única vez.
    ph_meter = _ok(
        lab.post(
            "/instruments",
            lab.admin,
            {
                "code": "PH-METER-01",
                "name": "pHmetro de bancada",
                "instrument_type": "PH_METER",
                "serial_number": "SN-0001",
                "calibration_due_date": NEXT_YEAR,
            },
        ),
        201,
    )
    instrument = {"X-Instrument-Key": ph_meter["api_key"]}
    assert _ok(client.post(f"{API}/instruments/heartbeat", headers=instrument))["can_measure"]

    # 2. Analista registra a amostra: código gerado e plano do produto com o limite
    #    próprio do produto (pH 5,5 a 7,0) copiado para a amostra.
    sample = lab.create_sample(priority="URGENT")
    sample_id = sample["id"]
    year = datetime.now(UTC).year
    assert sample["sample_code"] == f"SMP-{year}-0001"
    assert sample["status"] == "RECEIVED"
    tests = {test["test_code"]: test for test in sample["tests"]}
    assert set(tests) == {"PH", "DENSITY"}
    assert (Decimal(tests["PH"]["spec_min"]), Decimal(tests["PH"]["spec_max"])) == (
        Decimal("5.5"),
        Decimal("7.0"),
    )

    # 3. Fora de análise, a amostra não entra na worklist do equipamento.
    assert get("/instruments/worklist", instrument)["items"] == []
    _ok(lab.post(f"/samples/{sample_id}/start-analysis", lab.analyst))
    worklist = get("/instruments/worklist", instrument)["items"]
    assert [(item["sample_code"], item["test"]) for item in worklist] == [
        (sample["sample_code"], "PH")
    ]

    # 4. O pHmetro envia 7,4 (acima de 7,0): aceito e classificado como OOS.
    reading = {
        "instrument_id": "PH-METER-01",
        "sample_code": sample["sample_code"],
        "test": "PH",
        "result": "7.4",
        "unit": "pH",
    }
    accepted = _ok(client.post(f"{API}/instruments/results", headers=instrument, json=reading), 201)
    assert accepted["spec_status"] == "OOS"
    # Reenviar não sobrescreve: a mensagem é recusada e registrada.
    resend = client.post(f"{API}/instruments/results", headers=instrument, json=reading)
    assert _error(resend, 409) == "TEST_ALREADY_COMPLETED"
    assert _ok(lab.enter(sample, "DENSITY", "1.02"), 201)["spec_status"] == "IN_SPEC"

    # 5. Envio para revisão: resultados bloqueados; a aprovação é barrada pelo OOS.
    _ok(lab.post(f"/samples/{sample_id}/submit-for-review", lab.analyst))
    locked = lab.enter(sample, "PH", "6.9", reason="Tentativa após o envio")
    assert _error(locked, 409) == "SAMPLE_NOT_IN_ANALYSIS"
    blocked = lab.post(
        f"/samples/{sample_id}/approve", lab.reviewer, {"password": DEFAULT_PASSWORD}
    )
    assert _error(blocked, 409) == "SAMPLE_HAS_OOS_RESULTS"
    no_report = client.get(f"{API}/reports/samples/{sample_id}", headers=lab.reviewer)
    assert _error(no_report, 409) == "REPORT_NOT_AVAILABLE"

    # 6. Revisora devolve com justificativa; analista corrige, também com justificativa.
    _ok(
        lab.post(
            f"/samples/{sample_id}/return-to-analysis",
            lab.reviewer,
            {"reason": "Verificar a calibração do eletrodo antes da leitura"},
        )
    )
    corrected = _ok(
        lab.enter(sample, "PH", "6.9", reason="Eletrodo recalibrado; leitura repetida"), 201
    )
    assert (corrected["version"], corrected["spec_status"]) == (2, "IN_SPEC")
    _ok(lab.post(f"/samples/{sample_id}/submit-for-review", lab.analyst))

    # 7. Aprovação: o analista não tem permissão; senha errada não assina; a revisora
    #    (que não lançou resultados) aprova com a própria senha.
    by_analyst = lab.post(
        f"/samples/{sample_id}/approve", lab.analyst, {"password": DEFAULT_PASSWORD}
    )
    assert by_analyst.status_code == 403
    wrong = lab.post(f"/samples/{sample_id}/approve", lab.reviewer, {"password": "errada"})
    assert _error(wrong, 422) == "INVALID_SIGNATURE"
    approved = _ok(
        lab.post(
            f"/samples/{sample_id}/approve",
            lab.reviewer,
            {"password": DEFAULT_PASSWORD, "comment": "Correção documentada e conferida"},
        )
    )
    assert approved["status"] == "APPROVED"
    assert approved["reviewed_by"]["full_name"] == "Ana Souza"
    assert approved["allowed_actions"] == []

    # 8. Finalizada, a amostra não muda mais.
    edit = client.patch(
        f"{API}/samples/{sample_id}",
        json={"version": approved["version"], "notes": "ajuste tardio"},
        headers=lab.analyst,
    )
    assert _error(edit, 409) == "SAMPLE_NOT_EDITABLE"

    # 9. Histórico de status completo, na ordem.
    history = get(f"/samples/{sample_id}/status-history", lab.manager)
    assert [(item["from_status"], item["to_status"]) for item in history] == [
        (None, "RECEIVED"),
        ("RECEIVED", "IN_ANALYSIS"),
        ("IN_ANALYSIS", "AWAITING_REVIEW"),
        ("AWAITING_REVIEW", "IN_ANALYSIS"),
        ("IN_ANALYSIS", "AWAITING_REVIEW"),
        ("AWAITING_REVIEW", "APPROVED"),
    ]

    # 10. Relatório: o OOS corrigido continua visível; a emissão fica no audit trail.
    report = get(f"/reports/samples/{sample_id}", lab.manager)
    ph = next(test for test in report["tests"] if test["test_code"] == "PH")
    assert ph["had_oos"] is True
    assert [
        (version["version"], version["source"], version["spec_status"])
        for version in [*ph["previous_versions"], ph["result"]]
    ] == [(1, "INSTRUMENT", "OOS"), (2, "MANUAL", "IN_SPEC")]
    assert report["instruments"] == ["PH-METER-01"]
    pdf = client.get(f"{API}/reports/samples/{sample_id}/pdf", headers=lab.manager)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert pdf.headers["x-report-sha256"] == report["content_hash"]

    # 11. Timeline: cada passo relevante, com o ator certo, em ordem cronológica.
    timeline = get(f"/samples/{sample_id}/timeline", lab.analyst, size=100)["items"]
    steps = [(event["action"], event["actor_type"], event["actor_name"]) for event in timeline]
    assert steps == [
        ("SAMPLE_CREATED", "USER", "Carlos Silva"),
        ("TESTS_ASSIGNED", "USER", "Carlos Silva"),
        ("SAMPLE_STATUS_CHANGED", "USER", "Carlos Silva"),
        ("RESULT_ENTERED", "INSTRUMENT", "PH-METER-01"),
        ("INSTRUMENT_MESSAGE_REJECTED", "INSTRUMENT", "PH-METER-01"),
        ("RESULT_ENTERED", "USER", "Carlos Silva"),
        ("SAMPLE_STATUS_CHANGED", "USER", "Carlos Silva"),
        ("SAMPLE_STATUS_CHANGED", "USER", "Ana Souza"),
        ("RESULT_AMENDED", "USER", "Carlos Silva"),
        ("SAMPLE_STATUS_CHANGED", "USER", "Carlos Silva"),
        ("SAMPLE_STATUS_CHANGED", "USER", "Ana Souza"),
        ("REPORT_GENERATED", "USER", "Marcos Lima"),
    ]
    amended = next(event for event in timeline if event["action"] == "RESULT_AMENDED")
    assert amended["has_oos"] is True and amended["is_correction"] is True
    assert amended["old_value"]["spec_status"] == "OOS"

    # 12. A cadeia de hashes do audit trail continua íntegra depois de tudo.
    verification = get("/audit-logs/verify", lab.manager)
    assert verification["valid"] is True
    assert verification["checked_records"] >= len(timeline)

    # 13. Indicadores refletem a amostra aprovada e o OOS corrigido.
    summary = get("/dashboard/summary", lab.manager, period_days=7)
    assert summary["workload"]["open"] == 0
    current = summary["current"]
    assert (current["approved"], current["rejected"], current["approval_rate"]) == (1, 0, 1.0)
    assert (current["oos_results"], current["samples_with_oos"]) == (1, 1)
