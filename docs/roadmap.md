# Plano de implementação

O projeto é construído em 14 etapas incrementais. Cada etapa termina com o
sistema funcionando, testado e versionado.

| Etapa | Entrega                     | Status       |
| ----- | --------------------------- | ------------ |
| 1     | Arquitetura e estrutura     | ✅ Concluída |
| 2     | Banco de dados e modelos    | ✅ Concluída |
| 3     | Backend e API (fundação)    | ✅ Concluída |
| 4     | Autenticação e usuários     | ✅ Concluída |
| 5     | Samples e testes            | ✅ Concluída |
| 6     | Resultados e regras OOS     | ✅ Concluída |
| 7     | Audit trail                 | ✅ Concluída |
| 8     | Instrument Simulator        | ✅ Concluída |
| 9     | Frontend                    | ✅ Concluída |
| 10    | Dashboard                   | ✅ Concluída |
| 11    | Relatórios                  | ✅ Concluída |
| 12    | Testes                      | ✅ Concluída |
| 13    | Docker                      | ✅ Concluída |
| 14    | Documentação e apresentação | ✅ Concluída |

---

### ETAPA 1: Arquitetura e estrutura ✅
- Documentos: [arquitetura](architecture.md), [modelo de dados](database.md), [API](api.md), [ciclo da amostra](sample-lifecycle.md).
- Monorepo: `backend/`, `frontend/`, `instrument-simulator/`, `docs/`.
- Backend em camadas (`api`, `services`, `domain`, `repositories`, `models`, `schemas`, `database`, `core`) com *application factory*, configuração por ambiente, logs texto/JSON e health check.
- **Teste de arquitetura** que impede violações da regra de dependência entre camadas.
- Frontend Vite + React + TypeScript com a estrutura por features e proxy `/api` para o backend.

### ETAPA 2: Banco de dados e modelos ✅
- Enums do domínio.
- Base declarativa com convenção de nomes de constraints e *mixin* de timestamps.
- 13 modelos SQLAlchemy 2.0 com PKs, FKs, índices, `UNIQUE` e `CHECK`.
- Alembic + migração inicial (incluindo o trigger de imutabilidade do `audit_logs`).
- `docker-compose` com PostgreSQL para desenvolvimento.
- Testes de constraints (ex.: resultado sem autor é recusado pelo banco), de *optimistic locking* e, contra PostgreSQL real, do trigger do audit trail e da consistência entre modelos e migrações.

### ETAPA 3: Backend e API (fundação) ✅
- Sessão por requisição e controle de transação nos serviços.
- Hierarquia de exceções da aplicação + *handler* global com envelope de erro padrão.
- Middleware de `request_id` e log de acesso.
- Paginação e ordenação genéricas nos repositórios.
- `/health/ready` com verificação do banco.

### ETAPA 4: Autenticação e usuários ✅
- Hash de senha e JWT.
- Matriz de permissões (RBAC) no domínio + dependência `require_permission(...)`.
- Login, `/auth/me`, CRUD de usuários (desativação em vez de exclusão).
- `AuditService` com hash encadeado: a partir daqui, os serviços já registram eventos.
- Perfis criados por migração; comando `python -m app.cli create-admin` para o primeiro administrador.

### ETAPA 5: Samples e testes ✅
- Cadastros de clientes, produtos, tipos de teste e plano analítico por produto.
- Registro de amostra com código sequencial e atribuição automática de testes.
- Pesquisa com filtros e paginação.
- Máquina de estados + ações `start-analysis`, `submit-for-review`, `cancel`.

### ETAPA 6: Resultados e regras OOS ✅
- Avaliação de especificação (domínio, com `Decimal`).
- Registro manual de resultados e versionamento com justificativa.
- Revisão: `approve` (senha + quatro olhos + sem OOS), `reject`, `return-to-analysis`.
- Pesquisa de resultados vigentes e históricos, incluindo filtro OOS.
- Histórico OOS preservado (`had_oos`), mesmo após correção e aprovação.
- Testes de API para limites inclusivos, precisão decimal, permissões,
  versionamento, auditoria, bloqueios por status e fluxo completo de revisão.
- Resposta de aprovação/reprovação já inclui o revisor, sem exigir nova consulta.

### ETAPA 7: Audit trail ✅
- Hash encadeado (SHA-256) e verificação de integridade (`/audit-logs/verify`).
- Consulta com filtros.
- Endpoint da **Sample Timeline**.
- Consulta paginada com filtros combináveis, datas inclusivas em UTC e ordenação estável.
- Verificação completa em leitura por lotes, com identificação da primeira inconsistência.
- Timeline cronológica por amostra, com autoria preservada, correções e histórico OOS.
- Testes de permissões, paginação, filtros, adulteração de campos e encadeamento;
  limites da cadeia de hashes documentados. Sem rotas de escrita na auditoria.

### ETAPA 8: Instrument Simulator ✅
- Cadastro de instrumentos com chave de API (hash) e rotação de chave.
- Endpoints de integração: `worklist`, `results`, `heartbeat`; log de mensagens.
- Simulador CLI (um ou vários instrumentos, taxa de OOS configurável).
- **Dados de demonstração** gerados pelos próprios serviços (audit trail coerente): 20 amostras, 5 produtos, 4 clientes, 5 usuários, 6 equipamentos, 8 tipos de teste, com resultados variados e alguns OOS.
- Chave `lt_inst_...` de 256 bits exibida uma vez; banco guarda só o SHA-256
  (migração `0003`: hash único). Rotação auditada e com efeito imediato.
- RN-19 a RN-24 aplicadas na ordem documentada; toda mensagem de resultado,
  inclusive malformada, fica no log com o payload original. Recusas são
  auditadas e aparecem na timeline da amostra.
- Envios simultâneos serializados por bloqueio da amostra (testado contra
  PostgreSQL real): um é aceito e o outro recusado, nunca sobrescrito.
- `python -m app.cli seed-demo` com relógio controlado: histórico de 50 dias,
  cadeia de hashes válida, incidentes de integração reais (unidade errada,
  envio duplicado, calibração vencida, equipamento em manutenção) e amostras
  pendentes para o simulador.
- Simulador em `instrument-simulator/` (`run`, `worklist`, `send`,
  `heartbeat`), com testes unitários e ponta a ponta contra a API.

### ETAPA 9: Frontend ✅
- Layout corporativo com menu lateral (Dashboard, Samples, Tests, Results, Instruments, Audit Trail, Reports, Administration).
- Login, rotas protegidas por perfil, tabelas com filtros, badges de status, alertas de OOS.
- Detalhe da amostra com ações de workflow e **Sample Timeline** visual.
- Menu e rotas protegidos pela mesma configuração de permissões; sessão em
  `sessionStorage` validada em `/auth/me`, expiração tratada com aviso.
- Amostras: filtros na URL, progresso dos testes, registro com prévia do plano,
  lançamento com prévia OOS, correção com justificativa, histórico de versões,
  atribuição/cancelamento de testes, aprovação com senha e timeline agrupada por dia.
- Resultados (filtro OOS e versões corrigidas), catálogo de testes, equipamentos
  (chave exibida uma vez, rotação, log de mensagens), audit trail com verificação
  da cadeia, administração (usuários, clientes, produtos e plano analítico),
  dashboard básico e página de relatórios (PDF na ETAPA 11).
- Backend: progresso e `has_oos` na lista de amostras, `decimal_places` nos
  testes e resultados, limites próprios do produto no plano, ordenação por
  prioridade e status com significado de negócio, `created_at`/`updated_at`
  pelo relógio da aplicação.
- 49 testes Vitest com a aplicação real e a API simulada; validação visual com
  Chromium sobre os dados de demonstração, com todos os perfis.

### ETAPA 10: Dashboard ✅
- KPIs: amostras abertas, em análise, aguardando revisão, aprovadas, reprovadas, OOS, tempo médio de processamento.
- Gráficos: amostras por status, processadas por mês, % de aprovação, OOS por teste.
- `GET /dashboard/summary` e `GET /dashboard/charts` com período configurável
  (`period_days`), comparação com o período anterior, taxa de aprovação, tempo
  médio e mediano até a decisão e OOS contando versões corrigidas.
- Série diária, semanal ou mensal conforme o período, sem lacunas, agrupada no
  fuso do laboratório (`LABTRACK_LAB_TIMEZONE`; `tzdata` para Windows).
- Tela: carga atual acima do filtro; filtro de período único para indicadores
  e gráficos; variação com seta e texto (nunca só cor); gráficos Recharts com
  tooltip por mouse e teclado e tabela equivalente; carregamento sob demanda.
- Cores validadas com o validador de paleta: verde × vermelho reprovado para
  séries lado a lado (ΔE 4,1 em deuteranopia); aprovadas e reprovadas em azul
  e laranja (ΔE 24,7); vermelho de status só para OOS, com ícone e rótulo.
- Testes: domínio (janelas, fuso na virada do mês, taxas, tempos), API com
  cenário controlado e com os dados de demonstração, e Vitest da tela.

### ETAPA 11: Relatórios ✅
- Relatório da amostra (JSON + PDF): código, produto, lote, recebimento, testes, resultados, limites, status, analista, revisor, data de aprovação.
- Geração registrada no audit trail.
- Regras RN-27 (só amostras aprovadas ou reprovadas; `409 REPORT_NOT_AVAILABLE`
  nos demais status) e RN-28 (cada emissão do PDF registra `REPORT_GENERATED`
  com a impressão digital SHA-256 do conteúdo; a prévia em JSON não audita).
- `GET /reports/samples/{id}` (prévia) e `GET /reports/samples/{id}/pdf`
  (ReportLab, A4, cabeçalho e rodapé com "Página X de Y", emissão nº e
  impressão digital). O relatório mostra todas as versões dos resultados
  corrigidos, inclusive OOS, e os testes cancelados com justificativa.
- Tela de relatórios (lista de amostras revisadas, prévia com o mesmo conteúdo
  do PDF, emissão com download) e atalho no detalhe da amostra; a emissão
  aparece na Sample Timeline.
- Testes: domínio (formatação sem arredondar dígitos, fuso, impressão digital),
  API (permissões, disponibilidade, conteúdo, PDF lido com pypdf, audit e cadeia
  íntegra, relatório de várias páginas) e Vitest das telas.

### ETAPA 12: Testes ✅
- Cada etapa já entrega os testes do que implementa. Aqui, a cobertura é
  consolidada: fluxo ponta a ponta, cenários negativos de cada regra de
  negócio (RN-01 a RN-28) e testes contra PostgreSQL real.
- Pipeline de CI (lint + testes + build do frontend).
- Rastreabilidade: `@pytest.mark.rules("RN-xx")` nos testes e matriz gerada em
  [testing.md](testing.md); um teste falha se alguma regra ficar sem teste.
- Teste ponta a ponta do cadastro do equipamento ao relatório; cenários
  negativos que faltavam (cliente e teste inativos, teste concluído, amostra
  finalizada imutável em todas as operações, tolerância de relógio).
- `pytest --postgres` roda a suíte inteira no PostgreSQL com o schema das
  migrações; numeração concorrente de amostras verificada no banco real.
- Cobertura mínima: backend 95% com ramos (96,9% medido); frontend com piso de
  75% das linhas (de 51% para 79%, com testes das telas que faltavam).
- GitHub Actions: backend, backend no PostgreSQL 16, simulador e frontend.

### ETAPA 13: Docker ✅
- Dockerfiles *multi-stage* (backend e frontend com Nginx).
- `docker compose up` sobe banco, migrações, seed, API, frontend e simulador.
- Imagens sem root (UID 10001), dependências em camada própria, healthchecks;
  Nginx com rotas da SPA, cache dos arquivos com hash, cabeçalhos de segurança
  e proxy de `/api` e `/docs`.
- Inicialização idempotente: `seed-demo --if-empty` só gera a demonstração na
  primeira subida; as chaves do simulador ficam num volume compartilhado.
- Produção: a API recusa a chave JWT de desenvolvimento com
  `LABTRACK_ENVIRONMENT=production`; caminho documentado em
  [deployment.md](deployment.md).
- CI: job Docker constrói as imagens, sobe a stack e roda
  `scripts/smoke_test.py` duas vezes (primeira subida e subida com dados).

### ETAPA 14: Documentação e apresentação ✅
- README final com screenshots.
- Diagramas de arquitetura, ER e ciclo da amostra.
- Roteiro de apresentação de 5 minutos, decisões técnicas, perguntas prováveis de entrevista e respostas.
- README reorganizado por funcionalidade, com execução em Docker primeiro,
  passeio por oito capturas da stack Docker e números de qualidade.
- Diagramas: implantação (README, [deployment.md](deployment.md) e
  [architecture.md](architecture.md)), ER em [database.md](database.md) e
  máquina de estados em [sample-lifecycle.md](sample-lifecycle.md).
- [Apresentação](apresentacao.md): resumo de 30 segundos, roteiro de 5 minutos
  com as amostras da demonstração, decisões técnicas com alternativas e 12
  perguntas de entrevista com respostas.
- Correção encontrada nas capturas: valores longos (impressão digital) não
  transbordam mais a coluna de alterações do audit trail.
