"""Fixtures comuns.

Por padrão os testes de API usam SQLite em memória (rápidos, sem infraestrutura).
Com ``pytest --postgres`` eles rodam no PostgreSQL de ``LABTRACK_TEST_DATABASE_URL``,
com o schema recriado pelas migrações a cada teste (inclui o trigger do audit trail
e os perfis da migração 0002). Os testes marcados com ``postgres`` usam esse banco
sempre que a variável está definida.
"""

import os
from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

import app.models
from app.core.config import Settings
from app.core.security import hash_password
from app.database.base import Base
from app.database.session import build_engine
from app.domain.enums import RoleCode
from app.domain.permissions import ROLE_DEFINITIONS
from app.main import create_app
from app.models import Role, User

DEFAULT_PASSWORD = "Senha@2026"
SQLITE_URL = "sqlite+pysqlite:///:memory:"
POSTGRES_URL = os.getenv("LABTRACK_TEST_DATABASE_URL")

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


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--postgres",
        action="store_true",
        default=False,
        help="roda os testes de API no PostgreSQL de LABTRACK_TEST_DATABASE_URL",
    )


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("--postgres") and not POSTGRES_URL:
        raise pytest.UsageError("--postgres exige LABTRACK_TEST_DATABASE_URL")


def reset_postgres(url: str) -> None:
    """Schema vazio e todas as migrações aplicadas, como numa instalação nova."""
    from alembic import command
    from alembic.config import Config

    engine = build_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    finally:
        engine.dispose()
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


@pytest.fixture
def database_url(request: pytest.FixtureRequest) -> str:
    if not request.config.getoption("--postgres"):
        return SQLITE_URL
    assert POSTGRES_URL is not None
    reset_postgres(POSTGRES_URL)
    return POSTGRES_URL


@pytest.fixture
def settings(database_url: str) -> Settings:
    return Settings(environment="test", database_url=database_url, _env_file=None)


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
    Base.metadata.create_all(app.state.engine)  # no PostgreSQL, as migrações já criaram
    with app.state.session_factory() as session:
        roles = ensure_roles(session)
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


def ensure_roles(session: Session) -> dict[RoleCode, Role]:
    """Perfis do sistema: os da migração 0002 (PostgreSQL) ou criados aqui (SQLite)."""
    existing = {role.code: role for role in session.scalars(select(Role))}
    roles = {}
    for code, (name, description) in ROLE_DEFINITIONS.items():
        role = existing.get(code) or Role(code=code, name=name, description=description)
        session.add(role)
        roles[code] = role
    return roles
