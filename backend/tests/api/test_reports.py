"""Relatório da amostra pelo contrato HTTP: regras, conteúdo, PDF e audit trail."""

import re
from decimal import Decimal
from io import BytesIO
from typing import Any

import pytest
from fastapi import FastAPI
from pypdf import PdfReader

from app.core.config import Settings, get_settings

from ..conftest import DEFAULT_PASSWORD
from .conftest import API, Lab

PH_CORRECTION = "Erro de transcrição do valor lido"
MOISTURE_CANCELLATION = "Umidade não solicitada pelo cliente"
APPROVAL_COMMENT = "Resultados conferidos com o registro bruto"
REJECTION_REASON = "pH fora da especificação do produto"


def _report(lab: Lab, sample_id: int, headers: dict[str, str] | None = None) -> dict[str, Any]:
    response = lab.client.get(f"{API}/reports/samples/{sample_id}", headers=headers or lab.manager)
    assert response.status_code == 200, response.text
    return response.json()


def _pdf(lab: Lab, sample_id: int, headers: dict[str, str] | None = None) -> Any:
    response = lab.client.get(
        f"{API}/reports/samples/{sample_id}/pdf", headers=headers or lab.manager
    )
    assert response.status_code == 200, response.text
    return response


def _pages(content: bytes) -> list[str]:
    """Texto de cada página, com espaços normalizados (independe da quebra de linha)."""
    return [" ".join(page.extract_text().split()) for page in PdfReader(BytesIO(content)).pages]


def _emissions(lab: Lab, **params: Any) -> list[dict[str, Any]]:
    response = lab.client.get(
        f"{API}/audit-logs",
        headers=lab.manager,
        params={"action": "REPORT_GENERATED", "sort": "id", **params},
    )
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _approved_with_history(lab: Lab) -> dict[str, Any]:
    """Aprovada com um OOS corrigido e um teste cancelado."""
    sample = lab.create_sample()
    response = lab.post(
        f"/samples/{sample['id']}/tests",
        lab.analyst,
        {"test_definition_ids": [lab.tests["MOISTURE"]]},
    )
    assert response.status_code == 200, response.text
    sample = response.json()
    response = lab.post(
        f"/sample-tests/{lab.test_id(sample, 'MOISTURE')}/cancel",
        lab.analyst,
        {"reason": MOISTURE_CANCELLATION},
    )
    assert response.status_code == 200, response.text

    lab.analyze(sample, {"PH": "7.4", "DENSITY": "1.0215"})  # pH 7,4 fora (5,5 a 7,0)
    assert lab.enter(sample, "PH", "6.8", reason=PH_CORRECTION).status_code == 201
    lab.submit(sample)
    response = lab.post(
        f"/samples/{sample['id']}/approve",
        lab.reviewer,
        {"password": DEFAULT_PASSWORD, "comment": APPROVAL_COMMENT},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _rejected(lab: Lab) -> dict[str, Any]:
    sample = lab.create_sample()
    lab.analyze(sample, {"PH": "8.0", "DENSITY": "1.02"})
    lab.submit(sample)
    response = lab.post(
        f"/samples/{sample['id']}/reject", lab.reviewer, {"reason": REJECTION_REASON}
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def approved(lab: Lab) -> dict[str, Any]:
    return _approved_with_history(lab)


# --- Acesso e disponibilidade ---------------------------------------------------------


@pytest.mark.parametrize("role", ["analyst", "reviewer", "manager"])
def test_profiles_with_report_export_read_and_emit(
    lab: Lab, approved: dict[str, Any], role: str
) -> None:
    headers = getattr(lab, role)
    assert _report(lab, approved["id"], headers)["sample"]["sample_code"] == approved["sample_code"]
    assert _pdf(lab, approved["id"], headers).content.startswith(b"%PDF")


def test_admin_and_anonymous_have_no_access(lab: Lab, approved: dict[str, Any]) -> None:
    for suffix in ("", "/pdf"):
        path = f"{API}/reports/samples/{approved['id']}{suffix}"
        assert lab.client.get(path).status_code == 401
        response = lab.client.get(path, headers=lab.admin)
        assert response.status_code == 403
        assert response.json()["error"]["details"]["required_permission"] == "REPORT_EXPORT"
    assert _emissions(lab) == []


def test_unknown_sample(lab: Lab) -> None:
    for suffix in ("", "/pdf"):
        response = lab.client.get(f"{API}/reports/samples/999{suffix}", headers=lab.manager)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "SAMPLE_NOT_FOUND"


@pytest.mark.rules("RN-27")
def test_samples_not_yet_reviewed_have_no_report(lab: Lab) -> None:
    """RN-27: em andamento ou cancelada, não há relatório (nem registro de emissão)."""
    received = lab.create_sample()
    in_analysis = lab.create_sample()
    lab.analyze(in_analysis)
    awaiting = lab.create_sample()
    lab.analyze(awaiting)
    lab.submit(awaiting)
    cancelled = lab.create_sample()
    response = lab.post(
        f"/samples/{cancelled['id']}/cancel", lab.manager, {"reason": "Registro duplicado"}
    )
    assert response.status_code == 200, response.text

    for sample, status in (
        (received, "RECEIVED"),
        (in_analysis, "IN_ANALYSIS"),
        (awaiting, "AWAITING_REVIEW"),
        (cancelled, "CANCELLED"),
    ):
        for suffix in ("", "/pdf"):
            response = lab.client.get(
                f"{API}/reports/samples/{sample['id']}{suffix}", headers=lab.manager
            )
            assert response.status_code == 409, response.text
            error = response.json()["error"]
            assert error["code"] == "REPORT_NOT_AVAILABLE"
            assert error["details"]["status"] == status
    assert _emissions(lab) == []


# --- Conteúdo -------------------------------------------------------------------------


@pytest.mark.rules("RN-18")
def test_report_content_of_an_approved_sample(lab: Lab, approved: dict[str, Any]) -> None:
    report = _report(lab, approved["id"])

    assert report["lab_name"] == "Laboratório de Controle de Qualidade"
    assert report["timezone"] == "America/Sao_Paulo"
    assert report["generated_by"]["full_name"] == "Marcos Lima"
    assert re.fullmatch(r"[0-9a-f]{64}", report["content_hash"])

    sample = report["sample"]
    assert sample["sample_code"] == approved["sample_code"]
    assert sample["status"] == "APPROVED"
    assert sample["client"] == {"code": "CLI-001", "name": "Farmacêutica Aurora"}
    assert sample["product"] == {"code": "PRD-001", "name": "Xampu Neutro", "category": "Cosmético"}
    assert sample["lot_number"] == "L2026-0915"
    assert sample["registered_by"]["full_name"] == "Carlos Silva"
    assert sample["submitted_at"] is not None

    decision = report["decision"]
    assert decision["status"] == "APPROVED"
    assert decision["reviewed_by"]["full_name"] == "Ana Souza"
    assert decision["comment"] == APPROVAL_COMMENT
    assert decision["reviewed_at"] is not None

    tests = {test["test_code"]: test for test in report["tests"]}
    assert sorted(tests) == ["DENSITY", "MOISTURE", "PH"]

    ph = tests["PH"]
    assert (Decimal(ph["spec_min"]), Decimal(ph["spec_max"])) == (Decimal("5.5"), Decimal("7.0"))
    assert ph["method"] == "Potenciometria"
    assert ph["result"]["version"] == 2
    assert Decimal(ph["result"]["value"]) == Decimal("6.8")
    assert ph["result"]["spec_status"] == "IN_SPEC"
    assert ph["result"]["change_reason"] == PH_CORRECTION
    assert ph["result"]["entered_by"]["full_name"] == "Carlos Silva"
    assert [
        (version["version"], Decimal(version["value"]), version["spec_status"])
        for version in ph["previous_versions"]
    ] == [(1, Decimal("7.4"), "OOS")]
    assert ph["had_oos"] is True  # RN-18: o OOS corrigido continua no relatório

    density = tests["DENSITY"]
    assert Decimal(density["result"]["value"]) == Decimal("1.0215")
    assert density["previous_versions"] == []
    assert density["had_oos"] is False

    moisture = tests["MOISTURE"]
    assert moisture["status"] == "CANCELLED"
    assert moisture["result"] is None
    assert moisture["cancellation"]["cancelled_by"] == "Carlos Silva"
    assert moisture["cancellation"]["reason"] == MOISTURE_CANCELLATION

    assert report["summary"] == {
        "tests_reported": 2,
        "tests_cancelled": 1,
        "corrected_tests": 1,
        "current_oos": 0,
        "had_oos": True,
    }
    assert [user["full_name"] for user in report["analysts"]] == ["Carlos Silva"]
    assert report["instruments"] == []


def test_report_of_a_rejected_sample(lab: Lab) -> None:
    rejected = _rejected(lab)
    report = _report(lab, rejected["id"])

    assert report["decision"]["status"] == "REJECTED"
    assert report["decision"]["comment"] == REJECTION_REASON
    assert report["summary"]["current_oos"] == 1
    ph = next(test for test in report["tests"] if test["test_code"] == "PH")
    assert ph["result"]["spec_status"] == "OOS"


@pytest.mark.rules("RN-28")
def test_reading_the_report_is_not_audited_and_fingerprint_is_stable(
    lab: Lab, approved: dict[str, Any]
) -> None:
    first = _report(lab, approved["id"])
    second = _report(lab, approved["id"], lab.reviewer)

    assert first["content_hash"] == second["content_hash"]
    assert first["generated_by"] != second["generated_by"]
    assert _emissions(lab) == []


# --- PDF e audit trail ----------------------------------------------------------------


@pytest.mark.rules("RN-28")
def test_pdf_emission_is_audited_with_the_fingerprint(lab: Lab, approved: dict[str, Any]) -> None:
    content_hash = _report(lab, approved["id"])["content_hash"]
    response = _pdf(lab, approved["id"], lab.reviewer)

    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="relatorio-{approved["sample_code"]}.pdf"'
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-report-sha256"] == content_hash

    (emission,) = _emissions(lab)
    assert response.headers["x-report-emission"] == str(emission["id"])
    assert emission["actor_name"] == "Ana Souza"
    assert emission["entity_type"] == "sample"
    assert emission["entity_label"] == approved["sample_code"]
    assert emission["sample_id"] == approved["id"]
    assert emission["new_value"] == {
        "format": "PDF",
        "status": "APPROVED",
        "content_hash": content_hash,
    }

    timeline = lab.client.get(
        f"{API}/samples/{approved['id']}/timeline", headers=lab.reviewer, params={"size": 100}
    ).json()["items"]
    assert timeline[-1]["action"] == "REPORT_GENERATED"

    verification = lab.client.get(f"{API}/audit-logs/verify", headers=lab.manager).json()
    assert verification["valid"] is True


def test_pdf_content(lab: Lab, approved: dict[str, Any]) -> None:
    response = _pdf(lab, approved["id"])
    (text,) = _pages(response.content)
    emission = response.headers["x-report-emission"]

    for expected in (
        "Relatório de análise",
        approved["sample_code"],
        "APROVADA",
        "Farmacêutica Aurora (CLI-001)",
        "Xampu Neutro (PRD-001)",
        "L2026-0915",
        "Produção",
        "Alta",
        "6,80 pH",
        "corrigido (versão 2)",
        "5,50 a 7,00 pH",
        "1,0215 g/mL",  # 4 casas registradas, teste com 2: nenhum dígito escondido
        "1,00 a 1,05 g/mL",
        "Correções de resultados",
        "7,40 pH",
        "Fora da especificação",
        PH_CORRECTION,
        "Testes cancelados",
        MOISTURE_CANCELLATION,
        "Parecer da revisão",
        "Ana Souza",
        APPROVAL_COMMENT,
        "Resultados lançados por",
        "Marcos Lima",
        f"emissão nº {emission}",
        f"A emissão nº {emission} está registrada no audit trail",
        "America/Sao_Paulo",
        response.headers["x-report-sha256"],
        "Página 1 de 1",
    ):
        assert expected in text, expected

    metadata = PdfReader(BytesIO(response.content)).metadata
    assert metadata is not None
    assert metadata.title == f"Relatório de análise {approved['sample_code']}"


def test_pdf_of_a_rejected_sample(lab: Lab) -> None:
    rejected = _rejected(lab)
    (text,) = _pages(_pdf(lab, rejected["id"]).content)

    for expected in ("REPROVADA", "Justificativa da reprovação", REJECTION_REASON, "8,00 pH"):
        assert expected in text, expected
    assert "Fora da especificação" in text
    assert "Correções de resultados" not in text
    assert "Testes cancelados" not in text


@pytest.mark.rules("RN-28")
def test_every_emission_is_recorded_with_the_same_fingerprint(
    lab: Lab, approved: dict[str, Any]
) -> None:
    first = _pdf(lab, approved["id"], lab.analyst)
    second = _pdf(lab, approved["id"], lab.manager)

    assert first.headers["x-report-sha256"] == second.headers["x-report-sha256"]
    emissions = _emissions(lab)
    assert [item["actor_name"] for item in emissions] == ["Carlos Silva", "Marcos Lima"]
    assert [str(item["id"]) for item in emissions] == [
        first.headers["x-report-emission"],
        second.headers["x-report-emission"],
    ]


def test_long_reports_repeat_header_and_number_pages(lab: Lab) -> None:
    extra = {}
    for index in range(1, 31):
        response = lab.post(
            "/test-definitions",
            lab.admin,
            {
                "code": f"ASSAY-{index:02d}",
                "name": f"Teor do ativo {index:02d}",
                "unit": "%",
                "spec_min": 95,
                "spec_max": 105,
                "method": "HPLC, método interno",
            },
        )
        assert response.status_code == 201, response.text
        extra[f"ASSAY-{index:02d}"] = response.json()["id"]

    sample = lab.create_sample()
    response = lab.post(
        f"/samples/{sample['id']}/tests", lab.analyst, {"test_definition_ids": list(extra.values())}
    )
    assert response.status_code == 200, response.text
    sample = response.json()
    lab.analyze(sample, {**{code: "99.5" for code in extra}, "PH": "6.5", "DENSITY": "1.02"})
    lab.submit(sample)
    response = lab.post(
        f"/samples/{sample['id']}/approve", lab.reviewer, {"password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 200, response.text

    pages = _pages(_pdf(lab, sample["id"]).content)
    assert len(pages) >= 2
    for number, text in enumerate(pages, start=1):
        assert f"Página {number} de {len(pages)}" in text
        assert sample["sample_code"] in text
        assert "Teste e método" in text or number == len(pages)  # cabeçalho da tabela repetido
    assert all(f"Teor do ativo {index:02d}" in "".join(pages) for index in range(1, 31))


def test_lab_name_comes_from_settings(
    app: FastAPI, settings: Settings, lab: Lab, approved: dict[str, Any]
) -> None:
    custom = settings.model_copy(update={"lab_name": "Laboratório Central de Qualidade"})
    app.dependency_overrides[get_settings] = lambda: custom

    assert _report(lab, approved["id"])["lab_name"] == "Laboratório Central de Qualidade"
    (text,) = _pages(_pdf(lab, approved["id"]).content)
    assert "Laboratório Central de Qualidade" in text
