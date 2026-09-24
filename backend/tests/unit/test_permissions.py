import pytest

from app.domain.enums import RoleCode
from app.domain.permissions import ROLE_PERMISSIONS, Permission, has_permission, permissions_for

P = Permission


def test_every_role_has_permissions_defined() -> None:
    assert set(ROLE_PERMISSIONS) == set(RoleCode)


def test_every_permission_is_granted_to_some_role() -> None:
    granted = set().union(*ROLE_PERMISSIONS.values())
    assert granted == set(Permission)


@pytest.mark.parametrize(
    ("role", "permission"),
    [
        (RoleCode.ANALYST, P.RESULT_ENTER),
        (RoleCode.REVIEWER, P.SAMPLE_REVIEW),
        (RoleCode.ADMIN, P.USER_MANAGE),
        (RoleCode.ADMIN, P.TEST_DEFINITION_MANAGE),
        (RoleCode.MANAGER, P.SAMPLE_CANCEL),
    ],
)
def test_expected_grants(role: RoleCode, permission: Permission) -> None:
    assert has_permission(role, permission)


@pytest.mark.parametrize(
    ("role", "permission", "reason"),
    [
        (RoleCode.ADMIN, P.RESULT_ENTER, "administrador não manipula dados analíticos"),
        (RoleCode.ADMIN, P.SAMPLE_REVIEW, "administrador não aprova amostras"),
        (RoleCode.ANALYST, P.SAMPLE_REVIEW, "quem produz resultado não aprova"),
        (RoleCode.REVIEWER, P.RESULT_ENTER, "revisor não insere resultados"),
        (RoleCode.ANALYST, P.USER_MANAGE, "analista não gerencia usuários"),
        (RoleCode.ANALYST, P.AUDIT_READ, "audit trail restrito a supervisão"),
        (RoleCode.ANALYST, P.SAMPLE_CANCEL, "cancelamento é decisão gerencial"),
    ],
)
def test_segregation_of_duties(role: RoleCode, permission: Permission, reason: str) -> None:
    assert not has_permission(role, permission), reason


def test_unknown_role_has_no_permissions() -> None:
    assert permissions_for("HACKER") == frozenset()
