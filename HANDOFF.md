# LabTrack: relatório de continuidade (handoff)

Branch atual: `claude/festive-bell-x898pg` (repo GSHolanda/labtrack_gerenciamento_de_sistema).
As ETAPAS 1 a 7 vieram de `claude/inspiring-thompson-wefivy`.
Leia primeiro: `docs/architecture.md`, `docs/database.md`, `docs/api.md`,
`docs/sample-lifecycle.md` (regras RN-01 a RN-28) e `docs/roadmap.md`.

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
| 9 Frontend (todas as áreas do menu, timeline visual) | ✅ concluída e validada |
| 10 Dashboard (indicadores, séries, gráficos acessíveis) | ✅ concluída e validada |
| 11 Relatórios (prévia JSON, PDF auditado com impressão digital) | ✅ concluída e validada |
| 12 Testes (E2E, rastreabilidade RN, PostgreSQL, cobertura, CI) | ✅ concluída e validada |
| 13 Docker (imagens, compose completo, smoke test no CI) | ✅ concluída e validada |
| 14 Documentação final e apresentação | ✅ concluída |

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

## ETAPA 9: entrega concluída
- Frontend React 19 + TypeScript + Vite, React Router 8, TanStack Query 5,
  lucide-react; Vitest 5 + Testing Library (jsdom). CSS próprio com tokens
  (`src/styles/`), sem biblioteca de componentes. Ver `frontend/README.md`.
- `layouts/navigation.ts` é a fonte única de menu e proteção de rotas
  (`permissionsFor`); `features/auth/guards.tsx` (`RequireAuth`, `RequirePermission`).
- Sessão: token em `sessionStorage` (`features/auth/session.ts`, lido pelo cliente
  HTTP via `configureApi`), validado em `/auth/me`; 401 ou expiração → login com
  aviso e retorno à tela pedida; saída voluntária (`endedBy='manual'`) não guarda
  a origem.
- `api/client.ts`: `ApiError` (código, detalhes, `fieldErrors` de VALIDATION_ERROR,
  request id). `api/queryKeys.ts` centraliza as chaves; `features/samples/useSampleSync.ts`
  atualiza o detalhe e invalida listas, timeline e dashboard após cada operação.
- `lib/format.ts`: decimais tratados como texto (nunca arredonda dígitos
  registrados; vírgula na exibição e aceita na entrada), comparação com BigInt
  para a prévia OOS, datas UTC → fuso do navegador. `lib/labels.ts`: rótulos pt-BR.
- Telas: dashboard básico (contagens por status, OOS vigentes, fila do perfil),
  amostras (lista com filtros na URL, registro com prévia do plano, detalhe com
  ações, resultados, histórico de versões, atribuição/cancelamento de testes,
  aprovação com senha, timeline agrupada por dia), resultados, testes,
  equipamentos (chave exibida uma vez, rotação, log com payload), audit trail
  (verificação da cadeia, hashes), administração (usuários, clientes, produtos,
  editor do plano analítico) e relatórios (placeholder até a ETAPA 11).
- Backend ajustado para a interface: `tests_total`, `tests_completed`, `has_oos` na
  lista de amostras; `decimal_places` em `SampleTestRead` e `ResultListItem`;
  `product_spec_min/max` no plano; ordenação `priority` por nível e `status` pela
  sequência do workflow; `created_at`/`updated_at` com o relógio da aplicação
  (`database/base.py`), o que deixa a demonstração coerente também nessas colunas.
- Validação: roteiro no Chromium (Playwright) com todos os perfis sobre os dados de
  demonstração no PostgreSQL: registro → análise → OOS → correção → envio →
  senha errada recusada → aprovação; cancelamento pelo gestor; chave de
  equipamento; plano analítico. Sem erros de console além do 422 esperado da senha errada.

## ETAPA 10: entrega concluída
- Backend: `app/domain/dashboard.py` (granularidade dia ≤31 / semana ≤120 / mês
  conforme `period_days`; janelas semiabertas em UTC; `bucket_of` agrupa no fuso
  do laboratório, semana começando na segunda; `buckets_for` sem lacunas; taxa de
  aprovação; média e mediana do tempo até a decisão).
- `repositories/dashboard_repository.py`: contagens por status, urgentes em
  aberto, amostras abertas com resultado vigente OOS (teste não cancelado),
  concluídas no período, totais OOS (todas as versões, inclusive corrigidas) e
  resultados por teste; tudo com consultas agregadas.
- `services/dashboard_service.py` + `schemas/dashboard.py` +
  `api/v1/endpoints/dashboard.py`: `GET /dashboard/summary` (carga atual, totais do
  período e do período anterior) e `GET /dashboard/charts` (decisões e taxa por
  intervalo, amostras por status, OOS por teste), com `DASHBOARD_VIEW` e
  `period_days` 1–366 (padrão 30). Leitura não gera audit.
- Configuração `LABTRACK_LAB_TIMEZONE` (padrão `America/Sao_Paulo`, validada) e
  dependência `tzdata` para o Windows.
- Frontend: `features/dashboard/` com seção "Agora" (carga atual com links para a
  lista filtrada), filtro de período único na URL (`?period=7|30|90|365`, padrão
  90) acima de indicadores e gráficos, `StatTile` com variação contra o período
  anterior (seta + texto + "melhora/piora" para leitor de tela), `ChartCard`
  (legenda só com ≥2 séries, botão "Tabela" com os mesmos valores) e
  `DashboardCharts.tsx` com Recharts carregado sob demanda (`lazy`).
- Gráficos: decisões por intervalo (colunas empilhadas, 2px de espaço, ponta
  arredondada, ≤24px), taxa de aprovação (linha 0–100%, sem ligar intervalos sem
  decisão), amostras por status e OOS por teste (barras horizontais com rótulo na
  ponta). Nenhum eixo duplo; tooltip por mouse e por teclado (setas).
- Cores em `chartTheme.ts`, conferidas com o validador de paleta: azul `#2a78d6` ×
  laranja `#eb6834` passa (verde × vermelho foi reprovado para daltonismo); o
  vermelho de status `#d03b3b` só aparece em OOS, sempre com ícone e rótulo.
- Testes: domínio (fuso na virada do mês, buckets sem lacuna, 13 meses em 365
  dias), API (permissões dos 4 perfis, 401, 422, cenário completo, OOS corrigido,
  granularidade, sem audit), demonstração alimentando o dashboard, formatação e
  página no Vitest (período na URL, tabelas, aviso sem decisões).

## ETAPA 11: entrega concluída
- Regras RN-27 (relatório só para APPROVED/REJECTED; `409 REPORT_NOT_AVAILABLE`)
  e RN-28 (cada emissão do PDF grava `REPORT_GENERATED` com `{format, status,
  content_hash}`; a prévia JSON não audita), em `docs/sample-lifecycle.md`.
- `app/domain/report.py`: `ensure_reportable`, `content_fingerprint` (SHA-256 do
  JSON canônico via `to_audit_value`: `7.2100` = `7.21`, datas UTC com ou sem
  fuso), formatação pt-BR sem arredondar dígitos, faixa ("mín."/"máx.") e datas
  no fuso do laboratório.
- `schemas/reports.py` (`SampleReport`, `to_report_body`, `FINGERPRINT_FIELDS` =
  sample, decision, tests), `services/report_service.py` (JSON e emissão: audit
  na mesma transação, PDF gerado antes do commit) e `services/report_pdf.py`
  (ReportLab, Helvetica/WinAnsi com troca de símbolos, `BaseDocTemplate` com
  quadro sem recuo, `KeepTogether` no parecer, `_NumberedCanvas` para "Página X
  de Y"). `AuditRepository.sample_events` busca os cancelamentos de teste.
- `api/v1/endpoints/reports.py`: `GET /reports/samples/{id}` e `/pdf`
  (`Content-Disposition`, `Cache-Control: no-store`, `X-Report-SHA256`,
  `X-Report-Emission`, expostos no CORS). Configuração `LABTRACK_LAB_NAME`.
- Dependências: `reportlab` (runtime) e `pypdf` (dev, lê o texto dos PDFs nos testes).
- Frontend: `features/reports/` com `ReportsPage` (amostras revisadas, filtro de
  decisão, prévia e PDF por linha), `SampleReportPage` (`/reports/:id`, mesmo
  conteúdo e fuso do PDF, emissão com download e conferência da impressão
  digital), `useEmitReport` (download via `http.download`, toast, invalida
  timeline e audit); botão "Relatório" no detalhe da amostra; evento
  "Relatório emitido (PDF)" na timeline. `test/utils.tsx` aceita `Response` pronta.

## ETAPA 12: entrega concluída
- Estratégia e números em `docs/testing.md` (camadas, comandos, CI, matriz).
- Rastreabilidade: marcador `rules` (registrado no `pyproject.toml`, com
  `--strict-markers`); `tests/traceability.py` lê as RN de
  `docs/sample-lifecycle.md` e os marcadores via AST, gera a matriz
  (`python -m tests.traceability --write`) e `tests/unit/test_traceability.py`
  exige regra sem lacuna, IDs válidos e matriz em dia. Todas as 28 regras cobertas.
- `tests/api/test_end_to_end.py`: cenário único do cadastro do equipamento ao
  relatório, conferindo a timeline inteira (ação, tipo e nome do ator).
- Negativos novos em `test_samples.py` (cliente inativo, tolerância de relógio,
  teste inativo/inexistente, teste concluído, amostra final imutável em sete
  operações) e `test_postgres.py` (numeração concorrente de amostras).
- `pytest --postgres` (em `tests/conftest.py`): `database_url` recria o schema
  com as migrações a cada teste; `ensure_roles` reaproveita os perfis da
  migração 0002. Os testes de adulteração do audit trail (`test_audit.py`)
  confirmam o bloqueio do trigger e o desligam para provar a detecção pela cadeia.
- Cobertura: `pytest-cov` com `[tool.coverage]` (ramos, mínimo 95%);
  `@vitest/coverage-v8` com pisos em `vite.config.ts` e `npm run test:coverage`.
- Frontend: testes novos para audit trail, resultados, catálogo de testes,
  equipamentos, administração e ações com justificativa (reprovar, cancelar).
- CI: `.github/workflows/ci.yml` com os jobs backend, backend-postgres
  (serviço `postgres:16`), simulator e frontend.

## ETAPA 13: entrega concluída
- `backend/Dockerfile` (*multi-stage*, dependências lidas do `pyproject.toml`
  numa camada própria, virtualenv copiado para `python:3.11-slim`, usuário
  `labtrack` UID 10001, healthcheck em `/api/v1/health/ready`, Uvicorn com
  `--proxy-headers`), `backend/scripts/docker-init.sh` (migrações e, com
  `LABTRACK_SEED_DEMO=true`, `seed-demo --if-empty`).
- `frontend/Dockerfile` (Node 22 → Nginx 1.28, `VITE_DEMO_MODE` como build arg)
  e `frontend/nginx.conf` (SPA, `/assets` com cache longo, cabeçalhos de
  segurança, proxy de `/api/`, `/docs`, `/redoc`, `/healthz`).
- `instrument-simulator/Dockerfile` (mesmo UID para ler `/shared/config.json`).
- `docker-compose.yml`: `db` → `migrate` (tarefa única) → `api` (sem porta
  publicada, `FORWARDED_ALLOW_IPS=*`) → `frontend` (:8080) e `simulator`;
  volumes `labtrack-db-data` e `simulator-config`. `docker compose up -d db`
  continua servindo ao desenvolvimento local. `.env.example` na raiz.
- Backend: `DatabaseNotEmptyError` + `seed-demo --if-empty` (segunda subida não
  falha); `Settings` recusa a chave JWT de desenvolvimento em produção.
- `scripts/smoke_test.py` (só biblioteca padrão) e job `docker` no CI.
- Neste ambiente de nuvem, o Docker Hub respondeu 429: as imagens base vieram de
  `mirror.gcr.io` e o build local passou pelo proxy com variantes dos
  Dockerfiles fora do repositório (CA e proxy injetados). Os Dockerfiles do
  repositório são os padrão e são construídos sem ajustes no CI.

## ETAPA 14: entrega concluída
- README reescrito por funcionalidade: execução em Docker primeiro, oito
  capturas em `docs/images/` (tiradas da stack Docker com a demonstração),
  arquitetura, números de qualidade e desenvolvimento local; badge do CI
  apontando para a branch `claude/festive-bell-x898pg`.
- `docs/apresentacao.md`: resumo de 30 s, roteiro de 5 min (SMP-2026-0015 com
  OOS bloqueando a aprovação, SMP-2026-0016 aprovável pela `ana.souza`,
  SMP-2026-0005 com OOS corrigido), decisões com alternativas, 12 perguntas.
- Seção de implantação em `docs/architecture.md`; roadmap com as 14 etapas ✅.
- Correção: `.audit-change` com `overflow-wrap: anywhere` (hash longo
  transbordava sobre o botão "Detalhes").
- Relatórios das etapas 12, 13 e 14 em `docs/relatorios/`.

### Projeto concluído: próximos passos opcionais
1. Quando o usuário pedir: abrir PR de `claude/festive-bell-x898pg` para a
   branch principal (`claude/inspiring-thompson-wefivy` é a HEAD do remoto) e,
   depois do merge, tirar o `?branch=` do badge do CI no README.
2. Evoluções citadas na apresentação: SSO (OIDC), bloqueio por tentativas de
   login, notificações (OOS, amostras urgentes), relatórios por período e
   exportação CSV, multi-laboratório.
3. Commits das ETAPAS 1 a 5 têm autor Claude; reescrever só se o usuário pedir.

## Como rodar
```bash
docker compose up --build        # stack completa: http://localhost:8080 (ver docs/deployment.md)
docker compose up -d db          # só o banco, ou PostgreSQL local (user/senha/db: labtrack)
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
alembic upgrade head && python -m app.cli create-admin
# ou, num banco vazio: python -m app.cli seed-demo --simulator-config ../instrument-simulator/config.json
uvicorn app.main:app --reload    # /docs
pytest                            # SQLite em memória (pytest --cov: cobertura)
LABTRACK_TEST_DATABASE_URL=postgresql+psycopg://labtrack:labtrack@localhost:5432/labtrack_test pytest --postgres
ruff check . && ruff format --check .
cd ../instrument-simulator && pip install -e ".[dev]" && pytest
python -m simulator run --once   # com a API rodando e config.json gerado
cd ../frontend && npm install && npm run dev   # http://localhost:5173, proxy /api → :8000
npm test && npm run lint && npm run build
```
Validação da ETAPA 13: stack completa com `docker compose up --wait` (primeira
subida e subida com dados), `scripts/smoke_test.py` aprovado nas duas (16
verificações, com o simulador enviando resultados), interface Dockerizada no
Chromium (login com usuários de demonstração, dashboard, equipamentos online,
emissão do PDF, recarga de rota profunda) sem erros de console, IP do cliente
registrado no audit trail pelo proxy. Backend 469 testes em SQLite (96,9% de cobertura) e 475 com `--postgres`, simulador 41,
frontend 94. Relatório: `docs/relatorios/etapa-13.md`.

Validação da ETAPA 14: capturas conferidas uma a uma; a do audit trail revelou
o transbordo do hash, corrigido e verificado no Chromium (a célula termina antes
do botão). Frontend 94 testes, `tsc` e oxlint limpos; CI verde nas ETAPAS 12 e
13 (runs 1 e 3 no GitHub Actions, este último com o job Docker).

No Windows, o ambiente local já está em `backend/.venv`; use
`.\backend\.venv\Scripts\Activate.ps1` a partir da raiz ou execute diretamente
`.venv\Scripts\python.exe -m pytest` dentro de `backend/`.

## Convenções a manter
- Todo teste de regra de negócio leva `@pytest.mark.rules("RN-xx")`; depois de marcar,
  rode `python -m tests.traceability --write` (a matriz em `docs/testing.md` é conferida).
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
