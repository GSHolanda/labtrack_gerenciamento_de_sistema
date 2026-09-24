# LabTrack: relatório de continuidade (handoff)

Branch atual: `claude/festive-bell-x898pg` (repo GSHolanda/labtrack_gerenciamento_de_sistema).
As ETAPAS 1 a 7 vieram de `claude/inspiring-thompson-wefivy`.
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
| 8 Instrumentos, integração REST, simulador e demonstração | ✅ concluída e validada |
| 9 a 14 | pendentes (ver `docs/roadmap.md`) |

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

## ETAPA 8: entrega concluída
- Gestão (`InstrumentService`): `GET/POST /instruments`, `GET/PATCH /instruments/{id}`,
  `POST /instruments/{id}/rotate-key`, `GET /instruments/{id}/messages`. Chave
  `lt_inst_...` (256 bits) exibida só no cadastro/rotação; banco guarda SHA-256
  (`core/security.py`), migração `0003` torna o hash único. Código e tipo imutáveis;
  `calibration_due_date` obrigatória. Campos calculados `calibration_valid` e `online`
  (5 min). Auditoria sem chave nem hash (`INSTRUMENT_CREATED/UPDATED/KEY_ROTATED`).
- Integração (`InstrumentIntegrationService`), header `X-Instrument-Key`
  (`api/deps.py::get_current_instrument`): `GET /instruments/worklist`,
  `POST /instruments/results`, `POST /instruments/heartbeat`. O router de integração é
  registrado antes do de gestão (senão `/instruments/{id}` captura `worklist`).
- `results` recebe o corpo cru para registrar também mensagens malformadas
  (`INVALID_PAYLOAD`). Ordem das validações: payload → RN-19 → RN-20 → amostra →
  `IN_ANALYSIS` → teste atribuído → cancelado → RN-21 → `PENDING` → RN-23. Aceita:
  `ResultService.record()` + mensagem `ACCEPTED` + audit na mesma transação. Recusada:
  rollback, depois mensagem `REJECTED` + `INSTRUMENT_MESSAGE_REJECTED` (com `sample_id`
  se o código existe) em commit próprio; `details.message_id` no erro.
- Concorrência: `SampleRepository.find_by_code_for_update` (FOR UPDATE OF samples) e
  `IntegrityError` tratado como `TEST_ALREADY_COMPLETED`. Teste com threads no PostgreSQL.
- Regras puras em `domain/instruments.py`. Relógio da aplicação em `core/clock.py`
  (`utcnow`, `frozen_at`); serviços de audit, amostra e resultado passaram a usá-lo.
- Demonstração: `python -m app.cli seed-demo [--simulator-config caminho]` (`app/cli/demo.py`),
  só em banco vazio e fora de produção. Senha `Demo@2026` ou `LABTRACK_DEMO_PASSWORD`.
  20 amostras (10 aprovadas, 2 reprovadas, 3 aguardando revisão, 3 em análise,
  1 recebida, 1 cancelada), 5 produtos, 4 clientes, 5 usuários, 6 equipamentos,
  8 testes; histórico de 50 dias em ordem cronológica, correções, devolução para
  análise, OOS e 6 recusas reais de integração. `app/cli/admin.py::ensure_admin` é
  compartilhado com `create-admin`.
- Simulador em `instrument-simulator/` (httpx, sem acesso ao banco): `client.py`,
  `measurement.py`, `runner.py`, `config.py`, CLI `python -m simulator run|worklist|send|heartbeat`.
  `config.json` (com chaves) está no `.gitignore`; formato em `config.example.json`.
- Testes: 64 de API de instrumentos, 7 da demonstração, unitários de domínio, relógio
  e chave, constraint do hash, concorrência no PostgreSQL; simulador com 37 unitários
  e 4 ponta a ponta contra a API (pulados se o backend não estiver instalado).

### Próximos passos: ETAPA 9 (frontend)
1. Layout com menu lateral (Dashboard, Samples, Tests, Results, Instruments, Audit
   Trail, Reports, Administration), login e rotas protegidas por permissão
   (`GET /auth/me` já devolve as permissões).
2. Telas de amostras (lista com filtros, detalhe com ações de `allowed_actions`,
   lançamento/correção de resultados, alertas OOS e `had_oos`) e Sample Timeline visual
   (`GET /samples/{id}/timeline`, flags `is_correction` e `has_oos`).
3. Tela de equipamentos: lista com `online`/`calibration_valid`, cadastro e rotação
   mostrando a chave uma única vez, log de mensagens com filtro de status.
4. Usar os dados de `seed-demo` para desenvolver e demonstrar as telas.

## Como rodar
```bash
docker compose up -d db          # ou PostgreSQL local (user/senha/db: labtrack)
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
alembic upgrade head && python -m app.cli create-admin
# ou, num banco vazio: python -m app.cli seed-demo --simulator-config ../instrument-simulator/config.json
uvicorn app.main:app --reload    # /docs
pytest                            # SQLite em memória
LABTRACK_TEST_DATABASE_URL=postgresql+psycopg://labtrack:labtrack@localhost:5432/labtrack_test pytest
ruff check . && ruff format --check .
cd ../instrument-simulator && pip install -e ".[dev]" && pytest
python -m simulator run --once   # com a API rodando e config.json gerado
cd ../frontend && npm install && npm run build
```
Validação da ETAPA 8, com Python 3.11: backend **391 testes passando, nenhum
pulado**, incluindo os 5 de PostgreSQL 16 real (trigger append-only, migrações
0001–0003 iguais aos modelos, concorrência de resultados de instrumento).
Simulador: **41 testes passando** (inclui ponta a ponta contra a API). Ruff check
e format limpos nos dois pacotes. A demonstração também foi gerada no PostgreSQL
(cadeia de 184 registros válida, nenhum evento fora de ordem) e o simulador foi
executado como processo separado contra o uvicorn. Os testes de API usam SQLite
em memória; ele não preserva o fuso das datas, por isso as comparações
normalizam UTC.

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
- Horário de eventos de negócio sempre por `app.core.clock.utcnow()` (nunca `datetime.now`
  nos serviços); só o CLI de demonstração fixa o relógio (`frozen_at`).
- Segredos (chaves de instrumento) nunca vão para o audit trail nem para o banco em texto.
- Código em inglês, docs e mensagens em português. Commits por etapa, em nome do usuário
  (`gabriel <gabrielholanda606@gmail.com>`), sem linhas de coautoria.
