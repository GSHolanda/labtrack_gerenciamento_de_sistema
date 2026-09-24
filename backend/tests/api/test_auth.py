from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.audit import AuditAction
from app.domain.enums import RoleCode
from app.models import AuditLog, User

from ..conftest import DEFAULT_PASSWORD, LoginAs

LOGIN_URL = "/api/v1/auth/login"


def _login(client: TestClient, username: str, password: str = DEFAULT_PASSWORD):  # type: ignore[no-untyped-def]
    return client.post(LOGIN_URL, data={"username": username, "password": password})


def _audit(db: Session, action: AuditAction) -> list[AuditLog]:
    db.expire_all()
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action)))


def test_login_returns_token_and_permissions(client: TestClient, db: Session) -> None:
    response = _login(client, "carlos.silva")

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "ANALYST"
    assert "RESULT_ENTER" in body["user"]["permissions"]
    assert "SAMPLE_REVIEW" not in body["user"]["permissions"]


def test_login_is_case_insensitive_for_username(client: TestClient, db: Session) -> None:
    assert _login(client, "Carlos.Silva").status_code == 200


def test_successful_login_is_audited(client: TestClient, db: Session) -> None:
    _login(client, "ana.souza")

    [entry] = _audit(db, AuditAction.LOGIN_SUCCEEDED)
    assert entry.actor_name == "Ana Souza"
    assert entry.actor_type == "USER"
    assert entry.request_id is not None


def test_wrong_password_and_unknown_user_get_identical_response(
    client: TestClient, db: Session
) -> None:
    wrong_password = _login(client, "carlos.silva", "errada123")
    unknown_user = _login(client, "ninguem", "errada123")

    for response in (wrong_password, unknown_user):
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert wrong_password.json()["error"]["message"] == unknown_user.json()["error"]["message"]


def test_failed_logins_are_audited_with_reason(client: TestClient, db: Session) -> None:
    _login(client, "carlos.silva", "errada123")
    _login(client, "ninguem", "errada123")

    reasons = {entry.entity_label: entry.reason for entry in _audit(db, AuditAction.LOGIN_FAILED)}
    assert reasons == {"carlos.silva": "senha incorreta", "ninguem": "usuário inexistente"}


def test_inactive_user_cannot_log_in(client: TestClient, db: Session) -> None:
    user = db.scalars(select(User).where(User.username == "carlos.silva")).one()
    user.is_active = False
    db.commit()

    response = _login(client, "carlos.silva")

    assert response.status_code == 401
    assert _audit(db, AuditAction.LOGIN_FAILED)[0].reason == "usuário inativo"


def test_me_requires_token(client: TestClient, db: Session) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_me_rejects_invalid_token(client: TestClient, db: Session) -> None:
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer abc.def.ghi"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_me_returns_current_user(client: TestClient, login_as: LoginAs) -> None:
    response = client.get("/api/v1/auth/me", headers=login_as(RoleCode.REVIEWER))

    assert response.status_code == 200
    assert response.json()["username"] == "ana.souza"


def test_deactivation_revokes_existing_token_immediately(
    client: TestClient, db: Session, login_as: LoginAs
) -> None:
    headers = login_as(RoleCode.ANALYST)
    user = db.scalars(select(User).where(User.username == "carlos.silva")).one()
    user.is_active = False
    db.commit()

    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
