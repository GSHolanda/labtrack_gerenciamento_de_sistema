# LabTrack — Backend (API REST)

API do LabTrack construída com **FastAPI**, **SQLAlchemy** e **PostgreSQL**.
A arquitetura em camadas está descrita em [`docs/architecture.md`](../docs/architecture.md).

## Estrutura

```
app/
├── cli/            # Comandos administrativos (ex.: create-admin)
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
├── unit/           # Domínio, configuração, arquitetura e rastreabilidade das regras
├── api/            # Endpoints via TestClient, incluindo o fluxo ponta a ponta
├── db/             # Constraints; PostgreSQL: trigger do audit, migrações, concorrência
└── traceability.py # Matriz regra (RN-xx) → testes, publicada em docs/testing.md
```

## Executando localmente

```bash
docker compose up -d db            # PostgreSQL (na raiz do repositório)

cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head               # cria as tabelas e os perfis
python -m app.cli create-admin     # cria o usuário 'admin' (pede a senha)

uvicorn app.main:app --reload
```

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/api/v1/health

No Swagger, use o botão **Authorize** com o usuário e a senha para testar as
rotas protegidas.

## Banco de dados e migrações

```bash
alembic upgrade head                              # aplica as migrações
alembic revision --autogenerate -m "descrição"    # nova migração a partir dos modelos
alembic check                                     # confere se modelos e migrações batem
```

A migração inicial cria as 13 tabelas e, no PostgreSQL, o trigger que torna
`audit_logs` *append-only*. O modelo está documentado em
[`docs/database.md`](../docs/database.md).

## Qualidade

```bash
pytest                 # testes unitários, de API, de arquitetura e de banco (SQLite)
pytest --cov           # com cobertura (mínimo de 95%, com ramos)
export LABTRACK_TEST_DATABASE_URL=postgresql+psycopg://labtrack:labtrack@localhost:5432/labtrack_test
pytest                 # inclui testes que exigem PostgreSQL (trigger, migrações, concorrência)
pytest --postgres      # suíte inteira no PostgreSQL, schema recriado pelas migrações
ruff check .           # lint
ruff format --check .  # formatação
```

O teste `tests/unit/test_architecture.py` falha se alguma camada violar a regra
de dependência (por exemplo, importar FastAPI dentro de `services`), e
`tests/unit/test_traceability.py` falha se alguma regra de negócio ficar sem
teste marcado com `@pytest.mark.rules`. Veja [`docs/testing.md`](../docs/testing.md).
