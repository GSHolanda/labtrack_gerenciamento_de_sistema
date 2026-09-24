# syntax=docker/dockerfile:1
# Simulador de instrumentos: só conhece a API REST. Lê as chaves de /shared/config.json,
# gravado pela inicialização da demonstração.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN groupadd --system --gid 10001 labtrack \
    && useradd --system --uid 10001 --gid labtrack --home-dir /app --no-create-home labtrack
WORKDIR /app
COPY pyproject.toml README.md ./
COPY simulator ./simulator
RUN pip install .
USER labtrack
ENTRYPOINT ["python", "-m", "simulator"]
CMD ["run", "--config", "/shared/config.json"]
