from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.models
from app.core.config import Settings
from app.core.security import hash_password
from app.database.base import Base
from app.domain.enums import RoleCode
from app.domain.permissions import ROLE_DEFINITIONS
from app.main import create_app
from app.models import Role, User

DEFAULT_PASSWORD = "Senha@2026"

# Um usuário de demonstração por perfil.
DEMO_USERS = {
    RoleCode.ADMIN: ("admin", "Administrador do Sistema"),
    RoleCode.ANALYST: ("carlos.silva", "Carlos Silva"),
    RoleCode.REVIEWER: ("ana.souza", "Ana Souza"),
    RoleCode.MANAGER: ("marcos.lima", "Marcos Lima"),
}


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.security.BCRYPT_ROUNDS", 4)


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="test", database_url="sqlite+pysqlite:///:memory:", _env_file=None)


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db(app: FastAPI) -> Iterator[Session]:
    """Cria o schema e os dados de referência no banco da aplicação de teste."""
    Base.metadata.create_all(app.state.engine)
    with app.state.session_factory() as session:
        roles = {
            code: Role(code=code, name=name, description=description)
            for code, (name, description) in ROLE_DEFINITIONS.items()
        }
        password_hash = hash_password(DEFAULT_PASSWORD)
        for code, (username, full_name) in DEMO_USERS.items():
            session.add(
                User(
                    username=username,
                    email=f"{username}@labtrack.dev",
                    full_name=full_name,
                    password_hash=password_hash,
                    role=roles[code],
                )
            )
        session.commit()
        yield session


LoginAs = Callable[[RoleCode], dict[str, str]]


@pytest.fixture
def login_as(client: TestClient, db: Session) -> LoginAs:
    """Autentica com o usuário de demonstração do perfil e devolve o header Authorization."""

    def _login(role: RoleCode) -> dict[str, str]:
        username = DEMO_USERS[role][0]
        response = client.post(
            "/api/v1/auth/login", data={"username": username, "password": DEFAULT_PASSWORD}
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _login
