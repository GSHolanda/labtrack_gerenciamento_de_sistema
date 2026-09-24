"""Regras puras do relatório: quando emitir, impressão digital e formatação pt-BR."""

from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.core.exceptions import ConflictError
from app.domain.enums import SampleStatus
from app.domain.report import (
    content_fingerprint,
    ensure_reportable,
    format_decimal,
    format_moment,
    format_spec,
    is_reportable,
    report_filename,
)
from app.services.report_pdf import pdf_text

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


@pytest.mark.parametrize("status", [SampleStatus.APPROVED, SampleStatus.REJECTED])
def test_reviewed_samples_are_reportable(status: SampleStatus) -> None:
    assert is_reportable(status)
    ensure_reportable(status, "SMP-2026-0001")


@pytest.mark.parametrize(
    "status",
    [
        SampleStatus.RECEIVED,
        SampleStatus.IN_ANALYSIS,
        SampleStatus.AWAITING_REVIEW,
        SampleStatus.CANCELLED,
    ],
)
def test_other_statuses_have_no_report(status: SampleStatus) -> None:
    assert not is_reportable(status)
    with pytest.raises(ConflictError) as error:
        ensure_reportable(status, "SMP-2026-0001")
    assert error.value.code == "REPORT_NOT_AVAILABLE"
    assert error.value.details == {
        "status": status,
        "reportable_statuses": ["APPROVED", "REJECTED"],
    }


def test_fingerprint_ignores_representation_but_not_content() -> None:
    base = {
        "sample": {"code": "SMP-2026-0001", "received_at": datetime(2026, 9, 21, 13, 0)},
        "tests": [{"value": Decimal("7.2100")}],
    }
    same = {
        "tests": [{"value": Decimal("7.21")}],
        "sample": {
            "received_at": datetime(2026, 9, 21, 13, 0, tzinfo=UTC),
            "code": "SMP-2026-0001",
        },
    }
    changed = {**base, "tests": [{"value": Decimal("7.22")}]}

    fingerprint = content_fingerprint(base)
    assert len(fingerprint) == 64
    assert int(fingerprint, 16) >= 0
    assert content_fingerprint(same) == fingerprint
    assert content_fingerprint(changed) != fingerprint


@pytest.mark.parametrize(
    ("value", "places", "expected"),
    [
        (Decimal("7.2100"), 2, "7,21"),
        (Decimal("7.2150"), 2, "7,215"),  # nunca arredonda um dígito registrado
        (Decimal("0.5000"), 2, "0,50"),
        (Decimal("-0.0500"), 3, "-0,050"),
        (Decimal("12.0000"), 0, "12"),
        (Decimal("1.0000"), None, "1"),
        (Decimal("0010.5"), 1, "10,5"),
        (None, 2, "—"),
    ],
)
def test_format_decimal(value: Decimal | None, places: int | None, expected: str) -> None:
    assert format_decimal(value, places) == expected


def test_format_spec() -> None:
    assert format_spec(Decimal("5.5"), Decimal("7"), "pH", 2) == "5,50 a 7,00 pH"
    assert format_spec(None, Decimal("0.5"), "%", 2) == "máx. 0,50 %"
    assert format_spec(Decimal("95"), None, "%", 1) == "mín. 95,0 %"
    assert format_spec(None, None, "%", 1) == "—"


def test_format_moment_uses_the_lab_timezone() -> None:
    # 02:30 UTC de 1º de outubro ainda é 30 de setembro em São Paulo.
    assert format_moment(datetime(2026, 10, 1, 2, 30, tzinfo=UTC), SAO_PAULO) == "30/09/2026 23:30"
    assert format_moment(datetime(2026, 10, 1, 2, 30), SAO_PAULO) == "30/09/2026 23:30"
    assert format_moment(None, SAO_PAULO) == "—"


def test_pdf_text_escapes_markup_and_keeps_portuguese() -> None:
    assert pdf_text("USP <791> & ação, µS/cm, 25 °C") == (
        "USP &lt;791&gt; &amp; ação, µS/cm, 25 °C"
    )
    # Fora da codificação WinAnsi: equivalente legível ou "?".
    assert pdf_text("≤ 0,5 \u2212 1 Ω") == "&lt;= 0,5 - 1 ?"  # U+2212: sinal de menos


def test_report_filename() -> None:
    assert report_filename("SMP-2026-0007") == "relatorio-SMP-2026-0007.pdf"
