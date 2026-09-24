"""Agregador das rotas da versão 1 da API.

Cada módulo funcional (samples, results, instruments...) expõe um ``router``
em ``endpoints/`` e é registrado aqui, com sua tag no Swagger.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, master_data, samples, users

api_router = APIRouter()
api_router.include_router(health.router, tags=["System"])
api_router.include_router(auth.router, tags=["Authentication"])
api_router.include_router(users.router, tags=["Users"])
api_router.include_router(master_data.router)
api_router.include_router(samples.router)
