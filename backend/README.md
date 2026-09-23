# LabTrack — Backend (API REST)

API do LabTrack construída com **FastAPI**, **SQLAlchemy** e **PostgreSQL**.
A arquitetura em camadas está descrita em [`docs/architecture.md`](../docs/architecture.md).

## Estrutura

```
app/
├── api/            # Camada HTTP: rotas, dependências (auth, sessão), tradução de erros
│   └── v1/
│       ├── router.py
│       └── endpoints/
├── core/           # Configuração, logs, segurança, exceções (transversal)
├── database/       # Engine, sessão e base declarativa do SQLAlchemy
├── domain/         # Regras puras: enums, máquina de estados, avaliação OOS, permissões
├── models/         # Modelos ORM (tabelas)
├── repositories/   # Acesso a dados (consultas, filtros, paginação)
├── schemas/        # DTOs Pydantic (contratos da API)
├── services/       # Casos de uso e regras de negócio (transações, audit trail)
└── main.py         # Application factory
tests/
├── unit/           # Regras de domínio, configuração e testes de arquitetura
└── api/            # Testes dos endpoints via TestClient
```

## Executando localmente

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env

uvicorn app.main:app --reload
```

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/api/v1/health

## Qualidade

```bash
pytest                 # testes unitários, de API e de arquitetura
ruff check .           # lint
ruff format --check .  # formatação
```

O teste `tests/unit/test_architecture.py` falha se alguma camada violar a regra
de dependência (por exemplo, importar FastAPI dentro de `services`).
