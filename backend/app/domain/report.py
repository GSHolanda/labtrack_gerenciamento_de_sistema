"""Regras puras do relatório da amostra: quando emitir, impressão digital e formatação.

O relatório é o documento que sai do laboratório. Por isso só existe para amostras
já revisadas (RN-27) e cada emissão em PDF fica registrada no audit trail com a
impressão digital do conteúdo (RN-28): quem recebe o documento pode conferir, na
trilha, que ele corresponde ao que está no sistema.
"""

import hashlib
import json
from datetime import datetime, tzinfo
from decimal import Decimal
from typing import Any

from app.core.exceptions import ConflictError
from app.domain.audit import to_audit_value
from app.domain.dashboard import as_utc
from app.domain.enums import SampleStatus

REPORTABLE_STATUSES = frozenset({SampleStatus.APPROVED, SampleStatus.REJECTED})
EMPTY = "—"


def is_reportable(status: str) -> bool:
    return status in REPORTABLE_STATUSES


def ensure_reportable(status: str, sample_code: str) -> None:
    """RN-27: relatório só para amostras aprovadas ou reprovadas pelo revisor."""
    if not is_reportable(status):
        raise ConflictError(
            f"A amostra {sample_code} ainda não tem relatório: ele só é emitido depois da "
            "aprovação ou reprovação.",
            code="REPORT_NOT_AVAILABLE",
            details={"status": status, "reportable_statuses": sorted(REPORTABLE_STATUSES)},
        )


def content_fingerprint(content: dict[str, Any]) -> str:
    """SHA-256 do conteúdo do relatório em JSON canônico.

    Independe da representação: ``7.2100`` e ``7.21`` são o mesmo valor, e datas
    com ou sem fuso (UTC) produzem o mesmo texto. Duas emissões da mesma amostra
    finalizada têm a mesma impressão digital.
    """
    canonical = json.dumps(
        to_audit_value(content), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


# --- Formatação pt-BR (documento impresso) ------------------------------------------


def format_decimal(value: Decimal | None, places: int | None = None) -> str:
    """``7.2100`` com 2 casas → ``7,21``; ``7.2150`` → ``7,215``: nunca arredonda.

    Zeros à direita além das casas do teste são removidos e os que faltam são
    completados, como na interface.
    """
    if value is None:
        return EMPTY
    text = format(value, "f")
    sign = "-" if text.startswith("-") else ""
    integer, _, fraction = text.lstrip("-").partition(".")
    fraction = fraction.rstrip("0")
    if places is not None and len(fraction) < places:
        fraction = fraction.ljust(places, "0")
    integer = integer.lstrip("0") or "0"
    return f"{sign}{integer},{fraction}" if fraction else f"{sign}{integer}"


def format_spec(
    spec_min: Decimal | None, spec_max: Decimal | None, unit: str, places: int | None = None
) -> str:
    """Faixa de especificação por extenso: ``6,50 a 7,50 pH``, ``máx. 0,50 %``."""
    low = None if spec_min is None else format_decimal(spec_min, places)
    high = None if spec_max is None else format_decimal(spec_max, places)
    if low is not None and high is not None:
        return f"{low} a {high} {unit}"
    if high is not None:
        return f"máx. {high} {unit}"
    if low is not None:
        return f"mín. {low} {unit}"
    return EMPTY


def format_moment(moment: datetime | None, zone: tzinfo) -> str:
    """Data e hora no fuso do laboratório (datas sem fuso são UTC)."""
    if moment is None:
        return EMPTY
    return to_zone(moment, zone).strftime("%d/%m/%Y %H:%M")


def to_zone(moment: datetime, zone: tzinfo) -> datetime:
    return as_utc(moment).astimezone(zone)


def report_filename(sample_code: str) -> str:
    return f"relatorio-{sample_code}.pdf"
