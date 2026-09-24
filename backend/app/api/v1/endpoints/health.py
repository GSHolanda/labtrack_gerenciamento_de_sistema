from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app import __version__
from app.api.deps import DbSession
from app.core.config import Settings, get_settings
from app.schemas.health import HealthResponse, ReadinessResponse
from app.services.health_service import is_database_available

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness check",
    description="Indica se a API está no ar. Não consulta dependências externas.",
)
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=__version__,
        environment=settings.environment,
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse, "description": "Dependência indisponível"}},
    summary="Readiness check",
    description="Indica se a API está pronta para atender: verifica a conexão com o banco.",
)
def readiness(session: DbSession) -> ReadinessResponse | JSONResponse:
    database_ok = is_database_available(session)
    body = ReadinessResponse(
        status="ready" if database_ok else "unavailable",
        checks={"database": "ok" if database_ok else "unavailable"},
    )
    if database_ok:
        return body
    return JSONResponse(body.model_dump(), status_code=503)
