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
| 9 Frontend (todas as áreas do menu, timeline visual) | ✅ concluída e validada |
| 10 Dashboard (indicadores, séries, gráficos acessíveis) | ✅ concluída e validada |
| 11 a 14 | pendentes (ver `docs/roadmap.md`) |

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

### Próximos passos: ETAPA 11 (relatórios)
1. `GET /reports/samples/{id}` (JSON) e `GET /reports/samples/{id}/pdf` com
   `REPORT_EXPORT`: código, cliente, produto, lote, recebimento, testes,
   resultados vigentes (e se houve correção), limites, status OOS, analista,
   revisor e data de aprovação/reprovação. Definir se o relatório só sai para
   amostras finalizadas (APPROVED/REJECTED) e documentar a regra.
2. Registrar `REPORT_GENERATED` (já existe em `domain/audit.py`) na mesma
   transação, sem dados sensíveis; gerar o PDF no backend (ex.: ReportLab ou
   WeasyPrint; preferir dependência sem binários de sistema, pensando no Windows
   e no Docker da ETAPA 13).
3. Trocar o placeholder `frontend/src/features/reports/ReportsPage.tsx` (hoje lista
   amostras finalizadas) por prévia do relatório e download do PDF; botão também
   no detalhe da amostra para quem tem `REPORT_EXPORT`.

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
cd ../frontend && npm install && npm run dev   # http://localhost:5173, proxy /api → :8000
npm test && npm run lint && npm run build
```
Validação da ETAPA 10: backend **425 testes passando, nenhum pulado** (inclui os
de PostgreSQL 16 real), simulador **41**, frontend **63** (Vitest), Ruff,
oxlint, `tsc` e `vite build` limpos (Recharts fica num chunk separado,
`DashboardCharts-*.js`, baixado só ao abrir o dashboard). O dashboard foi
conferido no Chromium sobre a demonstração no PostgreSQL (7/30/90 dias e 12
meses, tabela equivalente, tooltip por mouse e teclado, largura de celular), sem
erros de console: 10 aprovadas, 2 reprovadas, taxa 83,3%, tempo médio ~2 d 3 h,
5 resultados OOS e 1 amostra em aberto com OOS vigente. Os testes de API usam
SQLite em memória; ele não preserva o fuso das datas, por isso as comparações
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
