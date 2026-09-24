#!/bin/sh
# Inicialização do banco no Docker: aplica as migrações e, na demonstração, gera os
# dados de exemplo e as chaves do simulador (só na primeira subida: --if-empty).
set -eu

alembic upgrade head

if [ "${LABTRACK_SEED_DEMO:-false}" = "true" ]; then
    python -m app.cli seed-demo --if-empty \
        --simulator-config /shared/config.json \
        --api-url "${LABTRACK_SIMULATOR_API_URL:-http://api:8000/api/v1}"
fi
