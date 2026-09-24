# LabTrack: relatório de continuidade (handoff)

Branch: `claude/inspiring-thompson-wefivy` (repo GSHolanda/labtrack_gerenciamento_de_sistema).
Leia primeiro: `docs/architecture.md`, `docs/database.md`, `docs/api.md`,
`docs/sample-lifecycle.md` (regras RN-01 a RN-26) e `docs/roadmap.md`.

## Decisões já aprovadas pelo usuário
- Camada extra `backend/app/domain/` (regras puras, sem FastAPI/SQLAlchemy).
- Tabela `product_specifications` (plano analítico por produto, com limites próprios).
- Rotas sob `/api/v1` (ex.: `POST /api/v1/instruments/results`).
- Admin não insere/aprova resultados; só o Gestor (MANAGER) cancela amostras.
- Instrumento só envia resultado para amostra IN_ANALYSIS e não sobrescreve resultado.

## Status das etapas
| Etapa | Status |
|---|---|
| 1 Arquitetura e estrutura | ✅ commitada |
| 2 Banco e modelos (13 tabelas, Alembic 0001, trigger append-only no audit) | ✅ commitada |
| 3 Fundação da API (erros padronizados, request id, sessão, paginação, /health/ready) | ✅ commitada |
| 4 Auth/usuários (bcrypt, JWT, RBAC, audit com hash encadeado, migração 0002 de perfis, `python -m app.cli create-admin`) | ✅ commitada |
| 5 Cadastros, amostras, workflow (start/submit/cancel) | ✅ commitada |
| 6 Resultados e OOS + revisão | ✅ concluída e validada |
| 7 Audit trail e Sample Timeline (API) | ✅ concluída e validada |
| 8 a 14 | pendentes (ver `docs/roadmap.md`) |

## ETAPA 6: entrega concluída
- `app/domain/specification.py::evaluate()` (OOS, limites inclusivos, Decimal) + testes unitários.
- `app/services/result_service.py`: `enter_manual()` e `record()` (reutilizável pela
  integração de instrumentos na ETAPA 8; não faz commit). Versionamento: correção exige
  `change_reason`, versão anterior fica `is_current=False`; audit RESULT_ENTERED/RESULT_AMENDED.
- `app/repositories/result_repository.py` (histórico e pesquisa com filtros).
- `app/schemas/results.py` (ResultEntry, ApproveRequest, ResultRead, ResultListItem).
- `SampleService.approve/reject/return_to_analysis` + `oos_tests()` e regra dos quatro olhos
  (`FOUR_EYES_VIOLATION`), senha na aprovação (`INVALID_SIGNATURE`), `SAMPLE_HAS_OOS_RESULTS`.
- Detalhe da amostra agora traz `current_result`, `result_versions`, `had_oos`, `oos_tests`.
- Rotas: `POST/GET /sample-tests/{id}/results`, `GET /results`,
  `POST /samples/{id}/approve|reject|return-to-analysis`.
- `UserReference` foi movido para `app/schemas/common.py`.
- Helpers `Lab.enter/analyze/submit` e `IN_SPEC_VALUES`; testes de amostras usam
  lançamentos reais pela API, sem completar testes diretamente no banco.
- `tests/api/test_results.py`: 46 cenários de API para resultados, OOS,
  versionamento, auditoria, permissões e revisão. Inclui operações recusadas
  sem efeitos colaterais, estados finais e reenvio após devolução.
- Corrigida a resposta de aprovação/reprovação: `reviewed_by` agora é atualizado
  pelo relacionamento ORM e aparece na própria resposta da ação.

## ETAPA 7: entrega concluída
- `GET /api/v1/audit-logs` com `AUDIT_READ`: filtros combináveis por usuário,
  instrumento, tipo de ator, ação, entidade, amostra e período inclusivo em UTC;
  paginação e ordenação estável. Nomes dos atores preservados como snapshot.
- `GET /api/v1/audit-logs/verify`: verifica toda a cadeia em ordem de ID, com
  leitura em lotes numa única consulta. Retorna a primeira inconsistência de
  conteúdo ou encadeamento. Não detecta remoção da cauda nem recálculo completo
  sem referência externa confiável; os limites estão documentados.
- `GET /api/v1/samples/{id}/timeline` com `SAMPLE_READ`: eventos cronológicos,
  paginados, derivados do audit trail, com flags `is_correction` e `has_oos`.
  Não expõe IP, request ID ou hashes; a interface visual fica para a ETAPA 9.
- `domain/audit.py`: `HASHED_FIELDS`, `ChainEntry`, `ChainVerification` e
  `verify_chain`. O cálculo de hash existente permanece compatível.
- Contratos em `schemas/audit.py`; consultas em `AuditRepository`; orquestração
  em `AuditService`; nenhuma rota de alteração ou exclusão da auditoria.
- 61 novos cenários de teste de domínio/API, incluindo filtros, permissões,
  adulteração, preservação de OOS, atores de instrumento/sistema e leitura sem escrita.

### Próximos passos: ETAPA 8
1. Criar gestão de instrumentos (cadastro, consulta, alteração e rotação de chave),
   com hash da chave e exibição do segredo apenas na criação/rotação.
2. Implementar autenticação `X-Instrument-Key` e integração `worklist`, `results`,
   `heartbeat` sob `/api/v1/instruments`. Aplicar RN-19 a RN-24: equipamento ativo,
   calibração válida, tipo/unidade compatíveis, amostra IN_ANALYSIS e teste PENDING.
3. Reutilizar `ResultService.record()` sem commit para gravar resultado, mensagem
   do instrumento e auditoria na mesma transação. Registrar mensagens rejeitadas
   com motivo; instrumento nunca sobrescreve resultado existente.
4. Criar o CLI separado em `instrument-simulator/`, comunicando apenas por HTTP,
   com um ou vários instrumentos e taxa OOS configurável.
5. Gerar demonstração pelos serviços: 20 amostras, 5 produtos, 4 clientes,
   5 usuários, 6 equipamentos e 8 testes, com resultados variados e histórico coerente.
6. Testar integração e regras negativas; atualizar documentação e fazer commit da etapa.

## Como rodar
```bash
docker compose up -d db          # ou PostgreSQL local (user/senha/db: labtrack)
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
alembic upgrade head && python -m app.cli create-admin
uvicorn app.main:app --reload    # /docs
pytest                            # SQLite em memória
LABTRACK_TEST_DATABASE_URL=postgresql+psycopg://labtrack:labtrack@localhost:5432/labtrack_test pytest
ruff check . && ruff format --check .
cd ../frontend && npm install && npm run build
```
Validação da ETAPA 7: **292 testes passando, 4 pulados**, Ruff check e format
limpos, com Python 3.11. Os quatro testes de PostgreSQL (trigger append-only e
consistência das migrações) não foram executados: `LABTRACK_TEST_DATABASE_URL`
não está definida. Os testes de API usam SQLite em memória; ele não preserva
o fuso das datas, por isso as comparações de resultados normalizam UTC.

No Windows, o ambiente local já está em `backend/.venv`; use
`.\backend\.venv\Scripts\Activate.ps1` a partir da raiz ou execute diretamente
`.venv\Scripts\python.exe -m pytest` dentro de `backend/`.

## Convenções a manter
- Regra de camadas verificada por `tests/unit/test_architecture.py` (api não importa
  repositories; services não importam FastAPI; domain puro). Filtros/paginação em
  `schemas`/`domain/pagination.py` para respeitar isso.
- Todo serviço grava audit na mesma transação (`AuditService.record`) e faz o commit.
- Erros: exceções de `app/core/exceptions.py` com `code` estável; nunca HTTPException em services.
- Decimais trafegam como texto; Python 3.11 (sem sintaxe genérica PEP 695).
- Código em inglês, docs e mensagens em português. Commits por etapa.
