# API REST

- **Base URL**: `/api/v1`
- **Formato**: JSON (UTF-8); datas em ISO 8601 com fuso (UTC)
- **Documentação interativa**: Swagger UI em `/docs` e ReDoc em `/redoc`
- **Autenticação de usuários**: `Authorization: Bearer <JWT>`
- **Autenticação de instrumentos**: `X-Instrument-Key: <chave do instrumento>`

## Perfis e permissões

A autorização é feita por **permissão**, não por perfil. Cada rota exige uma
permissão, e a matriz abaixo (definida na camada `domain`) diz quais perfis a
possuem. Mudar o que um perfil pode fazer é alterar uma linha da matriz.

| Permissão                | Administrador | Analista | Revisor | Gestor |
| ------------------------ | :-----------: | :------: | :-----: | :----: |
| `USER_MANAGE`            | ✔             |          |         |        |
| `MASTER_DATA_MANAGE`     | ✔             |          |         |        |
| `TEST_DEFINITION_MANAGE` | ✔             |          |         |        |
| `INSTRUMENT_MANAGE`      | ✔             |          |         |        |
| `SAMPLE_READ`            | ✔             | ✔        | ✔       | ✔      |
| `SAMPLE_CREATE`          |               | ✔        |         |        |
| `SAMPLE_ASSIGN_TESTS`    |               | ✔        |         |        |
| `SAMPLE_ANALYZE`         |               | ✔        |         |        |
| `RESULT_ENTER`           |               | ✔        |         |        |
| `SAMPLE_REVIEW`          |               |          | ✔       |        |
| `SAMPLE_CANCEL`          |               |          |         | ✔      |
| `AUDIT_READ`             | ✔             |          | ✔       | ✔      |
| `REPORT_EXPORT`          |               | ✔        | ✔       | ✔      |
| `DASHBOARD_VIEW`         | ✔             | ✔        | ✔       | ✔      |

> **Segregação de funções**: o administrador configura o sistema, mas não
> manipula dados analíticos; o analista produz resultados, mas não os aprova.

## Endpoints

### Sistema
| Método | Rota            | Acesso  | Descrição                                   |
| ------ | --------------- | ------- | ------------------------------------------- |
| GET    | `/health`       | público | *Liveness*: a API está no ar                |
| GET    | `/health/ready` | público | *Readiness*: API e banco disponíveis        |

### Autenticação
| Método | Rota          | Acesso      | Descrição                                          |
| ------ | ------------- | ----------- | -------------------------------------------------- |
| POST   | `/auth/login` | público     | Usuário e senha → JWT de acesso (tentativas são auditadas) |
| GET    | `/auth/me`    | autenticado | Usuário logado, perfil e permissões                |

### Usuários e perfis
| Método | Rota          | Permissão     | Descrição                                        |
| ------ | ------------- | ------------- | ------------------------------------------------ |
| GET    | `/users`      | `USER_MANAGE` | Lista com filtros (perfil, ativo, busca)         |
| POST   | `/users`      | `USER_MANAGE` | Cria usuário                                     |
| GET    | `/users/{id}` | `USER_MANAGE` | Detalhe                                          |
| PATCH  | `/users/{id}` | `USER_MANAGE` | Altera dados, perfil ou desativa (sem exclusão)  |
| GET    | `/roles`      | autenticado   | Perfis e suas permissões                         |

### Cadastros
| Método | Rota                             | Permissão                | Descrição                                  |
| ------ | -------------------------------- | ------------------------ | ------------------------------------------ |
| GET    | `/clients`                       | autenticado              | Lista clientes                             |
| POST   | `/clients`                       | `MASTER_DATA_MANAGE`     | Cria cliente                               |
| PATCH  | `/clients/{id}`                  | `MASTER_DATA_MANAGE`     | Altera / desativa cliente                  |
| GET    | `/products`                      | autenticado              | Lista produtos                             |
| POST   | `/products`                      | `MASTER_DATA_MANAGE`     | Cria produto                               |
| PATCH  | `/products/{id}`                 | `MASTER_DATA_MANAGE`     | Altera / desativa produto                  |
| GET    | `/products/{id}/specifications`  | autenticado              | Plano analítico do produto                 |
| PUT    | `/products/{id}/specifications`  | `MASTER_DATA_MANAGE`     | Define testes e limites do produto         |
| GET    | `/test-definitions`              | autenticado              | Lista tipos de teste                       |
| POST   | `/test-definitions`              | `TEST_DEFINITION_MANAGE` | Cria tipo de teste                         |
| GET    | `/test-definitions/{id}`         | autenticado              | Detalhe                                    |
| PATCH  | `/test-definitions/{id}`         | `TEST_DEFINITION_MANAGE` | Altera limites, método e equipamento (auditado) |

### Amostras e workflow
| Método | Rota                                  | Permissão             | Descrição                                                    |
| ------ | ------------------------------------- | --------------------- | ------------------------------------------------------------ |
| GET    | `/samples`                            | `SAMPLE_READ`         | Pesquisa paginada com filtros (ver abaixo)                   |
| POST   | `/samples`                            | `SAMPLE_CREATE`       | Registra amostra e atribui os testes do plano do produto     |
| GET    | `/samples/{id}`                       | `SAMPLE_READ`         | Detalhe com testes e resultados vigentes                     |
| PATCH  | `/samples/{id}`                       | `SAMPLE_CREATE`       | Altera dados de registro (exige `version`)                   |
| POST   | `/samples/{id}/tests`                 | `SAMPLE_ASSIGN_TESTS` | Atribui testes adicionais                                    |
| POST   | `/samples/{id}/start-analysis`        | `SAMPLE_ANALYZE`      | `RECEIVED` → `IN_ANALYSIS`                                   |
| POST   | `/samples/{id}/submit-for-review`     | `SAMPLE_ANALYZE`      | `IN_ANALYSIS` → `AWAITING_REVIEW`                            |
| POST   | `/samples/{id}/approve`               | `SAMPLE_REVIEW`       | `AWAITING_REVIEW` → `APPROVED` (exige senha)                 |
| POST   | `/samples/{id}/reject`                | `SAMPLE_REVIEW`       | `AWAITING_REVIEW` → `REJECTED` (exige justificativa)         |
| POST   | `/samples/{id}/return-to-analysis`    | `SAMPLE_REVIEW`       | `AWAITING_REVIEW` → `IN_ANALYSIS` (exige justificativa)      |
| POST   | `/samples/{id}/cancel`                | `SAMPLE_CANCEL`       | Estado não final → `CANCELLED` (exige justificativa)         |
| GET    | `/samples/{id}/status-history`        | `SAMPLE_READ`         | Histórico de mudanças de status                              |
| GET    | `/samples/{id}/timeline`              | `SAMPLE_READ`         | Linha do tempo completa (Sample Timeline)                    |

Filtros de `GET /samples`: `code`, `product_id`, `client_id`, `lot_number`,
`status` (múltiplo), `priority`, `responsible_id`, `received_from`,
`received_to`, `q` (busca livre), `page`, `size`, `sort` (ex.: `-received_at`).

As transições de status usam **rotas de ação** (`/approve`, `/reject`...) em vez
de um `PATCH status`. Cada ação tem permissão, validações e payload próprios, e
o Swagger documenta cada uma separadamente.

### Testes atribuídos e resultados
| Método | Rota                         | Permissão             | Descrição                                                          |
| ------ | ---------------------------- | --------------------- | ------------------------------------------------------------------ |
| POST   | `/sample-tests/{id}/cancel`  | `SAMPLE_ASSIGN_TESTS` | Cancela teste pendente (exige justificativa)                       |
| GET    | `/sample-tests/{id}/results` | `SAMPLE_READ`         | Todas as versões do resultado                                      |
| POST   | `/sample-tests/{id}/results` | `RESULT_ENTER`        | Registra resultado; se já existir, cria nova versão (exige `change_reason`) |
| GET    | `/results`                   | `SAMPLE_READ`         | Pesquisa de resultados (`spec_status=OOS`, fonte, teste, período)  |

### Instrumentos: gestão
| Método | Rota                          | Permissão           | Descrição                                          |
| ------ | ----------------------------- | ------------------- | -------------------------------------------------- |
| GET    | `/instruments`                | autenticado         | Equipamentos com status e última comunicação       |
| POST   | `/instruments`                | `INSTRUMENT_MANAGE` | Cadastra equipamento (chave exibida uma única vez) |
| GET    | `/instruments/{id}`           | autenticado         | Detalhe                                            |
| PATCH  | `/instruments/{id}`           | `INSTRUMENT_MANAGE` | Altera status, calibração, localização             |
| POST   | `/instruments/{id}/rotate-key`| `INSTRUMENT_MANAGE` | Gera nova chave de integração                      |
| GET    | `/instruments/{id}/messages`  | autenticado         | Log de mensagens recebidas (aceitas e rejeitadas)  |

### Instrumentos: integração (header `X-Instrument-Key`)
| Método | Rota                     | Descrição                                                          |
| ------ | ------------------------ | ------------------------------------------------------------------ |
| GET    | `/instruments/worklist`  | Testes pendentes compatíveis com o tipo do instrumento             |
| POST   | `/instruments/results`   | Envia um resultado                                                 |
| POST   | `/instruments/heartbeat` | Sinaliza que o equipamento está conectado                          |

Exemplo de envio:

```http
POST /api/v1/instruments/results
X-Instrument-Key: lt_inst_9f2c...
Content-Type: application/json

{
  "instrument_id": "PH-METER-01",
  "sample_code": "SMP-2026-0001",
  "test": "PH",
  "result": 7.21,
  "unit": "pH"
}
```

```json
201 Created
{
  "message_id": 318,
  "status": "ACCEPTED",
  "sample_code": "SMP-2026-0001",
  "test": "PH",
  "result": 7.21,
  "spec_status": "IN_SPEC",
  "spec_min": 6.5,
  "spec_max": 7.5
}
```

Rejeições possíveis (a mensagem é gravada como `REJECTED` com o código):

| Código                      | HTTP | Situação                                                   |
| --------------------------- | ---- | ---------------------------------------------------------- |
| `INSTRUMENT_ID_MISMATCH`    | 403  | `instrument_id` do corpo difere do dono da chave           |
| `INSTRUMENT_NOT_ACTIVE`     | 409  | Equipamento em manutenção ou inativo                       |
| `CALIBRATION_EXPIRED`       | 409  | Calibração vencida                                         |
| `SAMPLE_NOT_FOUND`          | 404  | Código de amostra inexistente                              |
| `SAMPLE_NOT_IN_ANALYSIS`    | 409  | Amostra não está em análise                                |
| `TEST_NOT_ASSIGNED`         | 409  | Teste não atribuído à amostra                              |
| `TEST_ALREADY_COMPLETED`    | 409  | Teste já tem resultado (correção só manual, com justificativa) |
| `INSTRUMENT_TYPE_MISMATCH`  | 409  | Tipo do equipamento incompatível com o teste               |
| `UNIT_MISMATCH`             | 422  | Unidade diferente da especificada                          |

### Audit trail
| Método | Rota                 | Permissão    | Descrição                                                                  |
| ------ | -------------------- | ------------ | -------------------------------------------------------------------------- |
| GET    | `/audit-logs`        | `AUDIT_READ` | Consulta paginada (usuário, ação, entidade, amostra, período)              |
| GET    | `/audit-logs/verify` | `AUDIT_READ` | Verifica a cadeia de hashes e aponta o primeiro registro adulterado        |

Não existem rotas `POST`, `PUT`, `PATCH` ou `DELETE` para o audit trail. Os
registros são criados apenas pelos serviços, como efeito das operações.

### Dashboard e relatórios
| Método | Rota                          | Permissão        | Descrição                                                       |
| ------ | ----------------------------- | ---------------- | --------------------------------------------------------------- |
| GET    | `/dashboard/summary`          | `DASHBOARD_VIEW` | KPIs: abertas, em análise, aguardando revisão, aprovadas, reprovadas, OOS, tempo médio |
| GET    | `/dashboard/charts`           | `DASHBOARD_VIEW` | Séries: por status, processadas por mês, % aprovação, OOS por teste |
| GET    | `/reports/samples/{id}`       | `REPORT_EXPORT`  | Dados do relatório da amostra (JSON)                            |
| GET    | `/reports/samples/{id}/pdf`   | `REPORT_EXPORT`  | Relatório em PDF (geração é auditada)                           |

## Convenções

### Valores decimais
Limites e resultados analíticos são serializados como **texto decimal**
(`"7.2000"`), não como número de ponto flutuante. O cliente recebe exatamente o
valor gravado no banco, sem arredondamentos de `float`. Na entrada, a API
aceita tanto número (`7.2`) quanto texto (`"7.2"`).

### Paginação
```json
{ "items": [ ... ], "total": 20, "page": 1, "size": 20, "pages": 1 }
```

### Formato de erro
Todos os erros seguem o mesmo envelope, gerado por um *handler* global:

```json
{
  "error": {
    "code": "SAMPLE_HAS_OOS_RESULTS",
    "message": "A amostra SMP-2026-0007 não pode ser aprovada: existem resultados fora da especificação.",
    "details": { "oos_tests": ["PH"] },
    "request_id": "8d1f5c0e-3b7a-4a57-9e8f-2f4b1f0c9a11"
  }
}
```

| HTTP | Uso                                                                                 |
| ---- | ----------------------------------------------------------------------------------- |
| 400  | Requisição malformada                                                               |
| 401  | Não autenticado (token ausente, inválido ou expirado; chave de instrumento inválida) |
| 403  | Autenticado, mas sem permissão                                                      |
| 404  | Recurso não encontrado                                                              |
| 409  | Conflito com o estado atual (transição inválida, regra de workflow, versão desatualizada) |
| 422  | Dados inválidos (validação de schema ou de negócio sobre o valor informado)         |
