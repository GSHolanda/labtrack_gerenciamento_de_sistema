import pytest

from app.core.exceptions import ConflictError
from app.domain.enums import SampleStatus
from app.domain.workflow import (
    ACTIONS_REQUIRING_REASON,
    TRANSITIONS,
    SampleAction,
    allowed_actions,
    ensure_editable,
    next_status,
)

S = SampleStatus
A = SampleAction


@pytest.mark.rules("RN-15")
@pytest.mark.parametrize(
    ("current", "action", "expected"),
    [
        (S.RECEIVED, A.START_ANALYSIS, S.IN_ANALYSIS),
        (S.IN_ANALYSIS, A.SUBMIT_FOR_REVIEW, S.AWAITING_REVIEW),
        (S.AWAITING_REVIEW, A.APPROVE, S.APPROVED),
        (S.AWAITING_REVIEW, A.REJECT, S.REJECTED),
        (S.AWAITING_REVIEW, A.RETURN_TO_ANALYSIS, S.IN_ANALYSIS),
        (S.RECEIVED, A.CANCEL, S.CANCELLED),
        (S.IN_ANALYSIS, A.CANCEL, S.CANCELLED),
        (S.AWAITING_REVIEW, A.CANCEL, S.CANCELLED),
    ],
)
def test_documented_transitions(current: S, action: A, expected: S) -> None:
    assert next_status(current, action) == expected


@pytest.mark.rules("RN-15")
def test_every_other_combination_is_rejected() -> None:
    for status in SampleStatus:
        for action in SampleAction:
            if (status, action) in TRANSITIONS:
                continue
            with pytest.raises(ConflictError) as error:
                next_status(status, action)
            assert error.value.code == "INVALID_STATUS_TRANSITION"


@pytest.mark.rules("RN-08", "RN-12")
@pytest.mark.parametrize(
    ("current", "action"),
    [
        (S.RECEIVED, A.APPROVE),  # não pula etapas
        (S.RECEIVED, A.SUBMIT_FOR_REVIEW),
        (S.IN_ANALYSIS, A.APPROVE),
        (S.APPROVED, A.CANCEL),  # estados finais não mudam (RN-14)
        (S.REJECTED, A.RETURN_TO_ANALYSIS),
        (S.CANCELLED, A.START_ANALYSIS),
    ],
)
def test_forbidden_shortcuts(current: S, action: A) -> None:
    with pytest.raises(ConflictError):
        next_status(current, action)


@pytest.mark.rules("RN-14")
@pytest.mark.parametrize("final", [S.APPROVED, S.REJECTED, S.CANCELLED])
def test_final_statuses_allow_no_action(final: S) -> None:
    assert allowed_actions(final) == []


@pytest.mark.rules("RN-13")
def test_reason_required_for_negative_actions() -> None:
    assert {A.REJECT, A.RETURN_TO_ANALYSIS, A.CANCEL} == ACTIONS_REQUIRING_REASON


@pytest.mark.rules("RN-05", "RN-14")
@pytest.mark.parametrize("status", [S.AWAITING_REVIEW, S.APPROVED, S.REJECTED, S.CANCELLED])
def test_sample_is_locked_outside_editable_statuses(status: S) -> None:
    with pytest.raises(ConflictError) as error:
        ensure_editable(status, "SMP-2026-0001")
    assert error.value.code == "SAMPLE_NOT_EDITABLE"
