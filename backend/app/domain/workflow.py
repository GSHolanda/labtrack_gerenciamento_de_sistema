"""Máquina de estados da amostra.

A tabela ``TRANSITIONS`` é a implementação literal do fluxo documentado em
``docs/sample-lifecycle.md``: qualquer combinação (status, ação) que não esteja
nela é recusada. As pré-condições que dependem de dados (testes concluídos,
resultados OOS etc.) são verificadas pelos serviços.
"""

from enum import StrEnum

from app.core.exceptions import ConflictError
from app.domain.enums import FINAL_SAMPLE_STATUSES, SampleStatus

S = SampleStatus


class SampleAction(StrEnum):
    START_ANALYSIS = "start_analysis"
    SUBMIT_FOR_REVIEW = "submit_for_review"
    APPROVE = "approve"
    REJECT = "reject"
    RETURN_TO_ANALYSIS = "return_to_analysis"
    CANCEL = "cancel"


TRANSITIONS: dict[tuple[SampleStatus, SampleAction], SampleStatus] = {
    (S.RECEIVED, SampleAction.START_ANALYSIS): S.IN_ANALYSIS,
    (S.IN_ANALYSIS, SampleAction.SUBMIT_FOR_REVIEW): S.AWAITING_REVIEW,
    (S.AWAITING_REVIEW, SampleAction.APPROVE): S.APPROVED,
    (S.AWAITING_REVIEW, SampleAction.REJECT): S.REJECTED,
    (S.AWAITING_REVIEW, SampleAction.RETURN_TO_ANALYSIS): S.IN_ANALYSIS,
    (S.RECEIVED, SampleAction.CANCEL): S.CANCELLED,
    (S.IN_ANALYSIS, SampleAction.CANCEL): S.CANCELLED,
    (S.AWAITING_REVIEW, SampleAction.CANCEL): S.CANCELLED,
}

# Ações que exigem justificativa (RN-13).
ACTIONS_REQUIRING_REASON = frozenset(
    {SampleAction.REJECT, SampleAction.RETURN_TO_ANALYSIS, SampleAction.CANCEL}
)

# Em quais status os dados de registro e os testes da amostra podem ser alterados.
EDITABLE_STATUSES = frozenset({S.RECEIVED, S.IN_ANALYSIS})


def next_status(current: str, action: SampleAction) -> SampleStatus:
    target = TRANSITIONS.get((SampleStatus(current), action))
    if target is None:
        raise ConflictError(
            f"A ação '{action}' não é permitida para uma amostra com status {current}.",
            code="INVALID_STATUS_TRANSITION",
            details={"current_status": current, "action": action},
        )
    return target


def allowed_actions(current: str) -> list[SampleAction]:
    """Ações possíveis a partir do status atual (a interface usa para exibir botões)."""
    status = SampleStatus(current)
    return [action for (origin, action) in TRANSITIONS if origin == status]


def is_final(status: str) -> bool:
    return SampleStatus(status) in FINAL_SAMPLE_STATUSES


def ensure_editable(status: str, sample_code: str) -> None:
    if SampleStatus(status) not in EDITABLE_STATUSES:
        raise ConflictError(
            f"A amostra {sample_code} não pode ser alterada no status {status}.",
            code="SAMPLE_NOT_EDITABLE",
            details={"status": status},
        )
