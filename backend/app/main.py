"""Ponto de entrada da API LabTrack.

Usa o padrão *application factory* (``create_app``) para que a aplicação possa
ser instanciada com configurações diferentes (desenvolvimento, testes,
produção) sem efeitos colaterais.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app import __version__
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging

API_DESCRIPTION = """
**LabTrack** é um Mini-LIMS (*Laboratory Information Management System*) que
acompanha o ciclo de vida de amostras laboratoriais: recebimento, atribuição de
testes, análise, resultados, revisão e aprovação — com audit trail completo e
integração com instrumentos via REST.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, fmt=settings.log_format)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=API_DESCRIPTION,
        openapi_url=f"{settings.api_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    # Garante que as dependências usem exatamente a configuração recebida.
    app.dependency_overrides[get_settings] = lambda: settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    return app


app = create_app()
