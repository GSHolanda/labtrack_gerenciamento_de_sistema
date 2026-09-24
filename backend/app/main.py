"""Ponto de entrada da API LabTrack.

Usa o padrão *application factory* (``create_app``) para que a aplicação possa
ser instanciada com configurações diferentes (desenvolvimento, testes,
produção) sem efeitos colaterais.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app import __version__
from app.api.errors import register_error_handlers
from app.api.middleware import RequestContextMiddleware
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.database.session import build_engine, build_session_factory
from app.schemas.common import ErrorResponse

API_DESCRIPTION = """
**LabTrack** é um Mini-LIMS (*Laboratory Information Management System*) que
acompanha o ciclo de vida de amostras laboratoriais: recebimento, atribuição de
testes, análise, resultados, revisão e aprovação — com audit trail completo e
integração com instrumentos via REST.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, fmt=settings.log_format)
    engine = build_engine(settings.database_url, echo=settings.database_echo)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=API_DESCRIPTION,
        openapi_url=f"{settings.api_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        responses={
            422: {"model": ErrorResponse, "description": "Dados inválidos"},
            500: {"model": ErrorResponse, "description": "Erro interno"},
        },
    )
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)
    # Garante que as dependências usem exatamente a configuração recebida.
    app.dependency_overrides[get_settings] = lambda: settings

    register_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    # Adicionado por último = camada mais externa: envolve inclusive o CORS.
    app.add_middleware(RequestContextMiddleware)

    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    return app


app = create_app()
