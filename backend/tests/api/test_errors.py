"""Envelope de erro padrão e rastreabilidade por request id."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import Settings
from app.core.exceptions import (
    AuthenticationError,
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from app.main import create_app


class Payload(BaseModel):
    value: float


def _raise(exc: Exception):  # type: ignore[no-untyped-def]
    def endpoint() -> None:
        raise exc

    return endpoint


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    app = create_app(settings)
    routes = {
        "not-found": NotFoundError("Amostra não encontrada.", code="SAMPLE_NOT_FOUND"),
        "conflict": ConflictError(
            "Transição inválida.", code="INVALID_STATUS_TRANSITION", details={"from": "APPROVED"}
        ),
        "rule": BusinessRuleError("Unidade incompatível.", code="UNIT_MISMATCH"),
        "auth": AuthenticationError("Token expirado."),
        "forbidden": PermissionDeniedError("Sem permissão."),
        "stale": StaleDataError("stale"),
        "boom": RuntimeError("segredo interno"),
    }
    for path, exc in routes.items():
        app.add_api_route(f"/test/{path}", _raise(exc), methods=["GET"])

    @app.post("/test/validate")
    def validate(payload: Payload) -> Payload:
        return payload

    return app


@pytest.fixture
def test_client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [
        ("not-found", 404, "SAMPLE_NOT_FOUND"),
        ("conflict", 409, "INVALID_STATUS_TRANSITION"),
        ("rule", 422, "UNIT_MISMATCH"),
        ("auth", 401, "NOT_AUTHENTICATED"),
        ("forbidden", 403, "PERMISSION_DENIED"),
        ("stale", 409, "CONCURRENT_MODIFICATION"),
    ],
)
def test_application_errors_use_standard_envelope(
    test_client: TestClient, path: str, status: int, code: str
) -> None:
    response = test_client.get(f"/test/{path}")

    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code
    assert error["message"]
    assert error["request_id"] == response.headers["x-request-id"]


def test_error_details_are_returned(test_client: TestClient) -> None:
    assert test_client.get("/test/conflict").json()["error"]["details"] == {"from": "APPROVED"}


def test_authentication_error_advertises_bearer_scheme(test_client: TestClient) -> None:
    assert test_client.get("/test/auth").headers["www-authenticate"] == "Bearer"


def test_unexpected_error_returns_500_without_leaking_internals(test_client: TestClient) -> None:
    response = test_client.get("/test/boom")

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    assert "segredo" not in response.text
    assert error["request_id"] == response.headers["x-request-id"]


def test_validation_errors_list_each_field(test_client: TestClient) -> None:
    response = test_client.post("/test/validate", json={"value": "abc"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"][0]["field"] == "body.value"


def test_unknown_route_uses_envelope(test_client: TestClient) -> None:
    response = test_client.get("/api/v1/nao-existe")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_request_id_is_propagated_from_client(test_client: TestClient) -> None:
    response = test_client.get("/test/not-found", headers={"X-Request-ID": "lims-trace-42"})

    assert response.headers["x-request-id"] == "lims-trace-42"
    assert response.json()["error"]["request_id"] == "lims-trace-42"


def test_invalid_request_id_is_replaced(test_client: TestClient) -> None:
    response = test_client.get("/api/v1/health", headers={"X-Request-ID": "<script>"})

    assert response.headers["x-request-id"] != "<script>"
    assert len(response.headers["x-request-id"]) == 32
