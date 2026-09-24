from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_ready_when_database_is_reachable(client: TestClient) -> None:
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok"}}


def test_not_ready_when_database_is_unreachable() -> None:
    settings = Settings(
        environment="test",
        database_url="postgresql+psycopg://x:x@127.0.0.1:1/nope?connect_timeout=1",
        _env_file=None,
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "unavailable"
