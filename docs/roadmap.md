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
| 7     | Audit trail                 | ⏳ Próxima   |
| 8     | Instrument Simulator        | Planejada    |
| 9     | Frontend                    | Planejada    |
| 10    | Dashboard                   | Planejada    |
| 11    | Relatórios                  | Planejada    |
| 12    | Testes                      | Planejada    |
| 13    | Docker                      | Planejada    |
| 14    | Documentação e apresentação | Planejada    |

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

### ETAPA 7: Audit trail
- Hash encadeado (SHA-256) e verificação de integridade (`/audit-logs/verify`).
- Consulta com filtros.
- Endpoint da **Sample Timeline**.

### ETAPA 8: Instrument Simulator
- Cadastro de instrumentos com chave de API (hash) e rotação de chave.
- Endpoints de integração: `worklist`, `results`, `heartbeat`; log de mensagens.
- Simulador CLI (um ou vários instrumentos, taxa de OOS configurável).
- **Dados de demonstração** gerados pelos próprios serviços (audit trail coerente): 20 amostras, 5 produtos, 4 clientes, 5 usuários, 6 equipamentos, 8 tipos de teste, com resultados variados e alguns OOS.

### ETAPA 9: Frontend
- Layout corporativo com menu lateral (Dashboard, Samples, Tests, Results, Instruments, Audit Trail, Reports, Administration).
- Login, rotas protegidas por perfil, tabelas com filtros, badges de status, alertas de OOS.
- Detalhe da amostra com ações de workflow e **Sample Timeline** visual.

### ETAPA 10: Dashboard
- KPIs: amostras abertas, em análise, aguardando revisão, aprovadas, reprovadas, OOS, tempo médio de processamento.
- Gráficos: amostras por status, processadas por mês, % de aprovação, OOS por teste.

### ETAPA 11: Relatórios
- Relatório da amostra (JSON + PDF): código, produto, lote, recebimento, testes, resultados, limites, status, analista, revisor, data de aprovação.
- Geração registrada no audit trail.

### ETAPA 12: Testes
- Cada etapa já entrega os testes do que implementa. Aqui, a cobertura é
  consolidada: fluxo ponta a ponta, cenários negativos de cada regra de
  negócio (RN-01 a RN-26) e testes contra PostgreSQL real.
- Pipeline de CI (lint + testes + build do frontend).

### ETAPA 13: Docker
- Dockerfiles *multi-stage* (backend e frontend com Nginx).
- `docker compose up` sobe banco, migrações, seed, API, frontend e simulador.

### ETAPA 14: Documentação e apresentação
- README final com screenshots.
- Diagramas de arquitetura, ER e ciclo da amostra.
- Roteiro de apresentação de 5 minutos, decisões técnicas, perguntas prováveis de entrevista e respostas.
