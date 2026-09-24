# syntax=docker/dockerfile:1
# API do LabTrack. Build em duas fases: dependências e pacote num virtualenv, depois
# uma imagem enxuta só com o virtualenv, as migrações e um usuário sem privilégios.

# --- build ------------------------------------------------------------------------
FROM python:3.11-slim AS build
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH=/opt/venv/bin:$PATH
RUN python -m venv /opt/venv
WORKDIR /build
COPY pyproject.toml README.md ./
# Dependências numa camada própria: mudar o código não reinstala as bibliotecas.
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" > requirements.txt \
    && pip install -r requirements.txt
COPY app ./app
RUN pip install --no-deps .

# --- runtime ----------------------------------------------------------------------
FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    LABTRACK_LOG_FORMAT=json
RUN groupadd --system --gid 10001 labtrack \
    && useradd --system --uid 10001 --gid labtrack --home-dir /app --no-create-home labtrack \
    # Volume compartilhado com o simulador (chaves geradas pela demonstração).
    && mkdir -p /shared && chown labtrack:labtrack /shared
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts/docker-init.sh ./scripts/
USER labtrack
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=6 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/ready', timeout=3)"]
# --proxy-headers: o IP registrado no audit trail é o do cliente, não o do Nginx
# (confiando nos IPs de FORWARDED_ALLOW_IPS).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
