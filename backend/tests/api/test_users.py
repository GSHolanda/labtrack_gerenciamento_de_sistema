import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.audit import AuditAction
from app.domain.enums import RoleCode
from app.models import AuditLog, User

from ..conftest import LoginAs

USERS_URL = "/api/v1/users"
NEW_USER = {
    "username": "julia.costa",
    "email": "Julia.Costa@labtrack.dev",
    "full_name": "Júlia Costa",
    "password": "Segura@123",
    "role": "ANALYST",
}


def _user_id(db: Session, username: str) -> int:
    return db.scalars(select(User.id).where(User.username == username)).one()


def _last_audit(db: Session, action: AuditAction) -> AuditLog:
    db.expire_all()
    return db.scalars(
        select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id.desc())
    ).first()  # type: ignore[return-value]


@pytest.mark.parametrize("role", [RoleCode.ANALYST, RoleCode.REVIEWER, RoleCode.MANAGER])
def test_only_admin_manages_users(client: TestClient, login_as: LoginAs, role: RoleCode) -> None:
    response = client.get(USERS_URL, headers=login_as(role))

    assert response.status_code == 403
    assert response.json()["error"]["details"]["required_permission"] == "USER_MANAGE"


def test_admin_creates_user_and_action_is_audited(
    client: TestClient, db: Session, login_as: LoginAs
) -> None:
    response = client.post(USERS_URL, json=NEW_USER, headers=login_as(RoleCode.ADMIN))

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "julia.costa@labtrack.dev"
    assert body["role"] == "ANALYST"
    assert "password" not in body and "password_hash" not in body

    entry = _last_audit(db, AuditAction.USER_CREATED)
    assert entry.actor_name == "Administrador do Sistema"
    assert entry.new_value["username"] == "julia.costa"
    assert "password" not in str(entry.new_value)


def test_new_user_can_log_in(client: TestClient, login_as: LoginAs) -> None:
    client.post(USERS_URL, json=NEW_USER, headers=login_as(RoleCode.ADMIN))

    response = client.post(
        "/api/v1/auth/login", data={"username": "julia.costa", "password": "Segura@123"}
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("username", "CARLOS.SILVA", "USERNAME_ALREADY_EXISTS"),
        ("email", "ana.souza@labtrack.dev", "EMAIL_ALREADY_EXISTS"),
    ],
)
def test_duplicate_username_or_email_is_rejected(
    client: TestClient, login_as: LoginAs, field: str, value: str, code: str
) -> None:
    response = client.post(
        USERS_URL, json={**NEW_USER, field: value}, headers=login_as(RoleCode.ADMIN)
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == code


@pytest.mark.parametrize(
    "override",
    [{"email": "nao-e-email"}, {"password": "curta"}, {"role": "ROOT"}, {"username": "a b"}],
)
def test_invalid_user_data_is_rejected(
    client: TestClient, login_as: LoginAs, override: dict[str, str]
) -> None:
    response = client.post(
        USERS_URL, json={**NEW_USER, **override}, headers=login_as(RoleCode.ADMIN)
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_records_only_changed_fields(
    client: TestClient, db: Session, login_as: LoginAs
) -> None:
    user_id = _user_id(db, "carlos.silva")
    response = client.patch(
        f"{USERS_URL}/{user_id}",
        json={"role": "REVIEWER", "full_name": "Carlos Silva"},
        headers=login_as(RoleCode.ADMIN),
    )

    assert response.status_code == 200
    entry = _last_audit(db, AuditAction.USER_UPDATED)
    assert entry.old_value == {"role": "ANALYST"}
    assert entry.new_value == {"role": "REVIEWER"}


def test_password_reset_is_audited_without_exposing_values(
    client: TestClient, db: Session, login_as: LoginAs
) -> None:
    user_id = _user_id(db, "carlos.silva")
    client.patch(
        f"{USERS_URL}/{user_id}", json={"password": "NovaSenha@1"}, headers=login_as(RoleCode.ADMIN)
    )

    entry = _last_audit(db, AuditAction.USER_UPDATED)
    assert entry.new_value == {"password": "redefinida"}
    assert "NovaSenha" not in str(entry.old_value) + str(entry.new_value)


@pytest.mark.rules("RN-25")
def test_deactivated_user_cannot_log_in(client: TestClient, db: Session, login_as: LoginAs) -> None:
    user_id = _user_id(db, "carlos.silva")
    response = client.patch(
        f"{USERS_URL}/{user_id}", json={"is_active": False}, headers=login_as(RoleCode.ADMIN)
    )

    assert response.json()["is_active"] is False
    login = client.post(
        "/api/v1/auth/login", data={"username": "carlos.silva", "password": "Senha@2026"}
    )
    assert login.status_code == 401


@pytest.mark.rules("RN-25")
@pytest.mark.parametrize("change", [{"is_active": False}, {"role": "ANALYST"}])
def test_admin_cannot_lock_themselves_out(
    client: TestClient, db: Session, login_as: LoginAs, change: dict[str, object]
) -> None:
    response = client.patch(
        f"{USERS_URL}/{_user_id(db, 'admin')}", json=change, headers=login_as(RoleCode.ADMIN)
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SELF_MODIFICATION_NOT_ALLOWED"


@pytest.mark.rules("RN-25")
def test_users_cannot_be_deleted(client: TestClient, db: Session, login_as: LoginAs) -> None:
    response = client.delete(
        f"{USERS_URL}/{_user_id(db, 'carlos.silva')}", headers=login_as(RoleCode.ADMIN)
    )

    assert response.status_code == 405


def test_list_filters_and_paginates(client: TestClient, login_as: LoginAs) -> None:
    headers = login_as(RoleCode.ADMIN)

    by_role = client.get(USERS_URL, params={"role": "REVIEWER"}, headers=headers).json()
    assert [user["username"] for user in by_role["items"]] == ["ana.souza"]

    page = client.get(USERS_URL, params={"size": 2, "sort": "username"}, headers=headers).json()
    assert page["total"] == 4 and page["pages"] == 2
    assert [user["username"] for user in page["items"]] == ["admin", "ana.souza"]


def test_unknown_user_returns_404(client: TestClient, login_as: LoginAs) -> None:
    response = client.get(f"{USERS_URL}/9999", headers=login_as(RoleCode.ADMIN))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"


def test_roles_endpoint_exposes_permission_matrix(client: TestClient, login_as: LoginAs) -> None:
    roles = client.get("/api/v1/roles", headers=login_as(RoleCode.ANALYST)).json()

    by_code = {role["code"]: role for role in roles}
    assert set(by_code) == {"ADMIN", "ANALYST", "REVIEWER", "MANAGER"}
    assert "SAMPLE_REVIEW" in by_code["REVIEWER"]["permissions"]
