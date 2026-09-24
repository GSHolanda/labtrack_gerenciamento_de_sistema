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
| GET    | `/instruments`                | autenticado         | Equipamentos com status, calibração e última comunicação |
| POST   | `/instruments`                | `INSTRUMENT_MANAGE` | Cadastra equipamento (chave exibida uma única vez) |
| GET    | `/instruments/{id}`           | autenticado         | Detalhe                                            |
| PATCH  | `/instruments/{id}`           | `INSTRUMENT_MANAGE` | Altera status, calibração, localização e dados cadastrais |
| POST   | `/instruments/{id}/rotate-key`| `INSTRUMENT_MANAGE` | Gera nova chave de integração                      |
| GET    | `/instruments/{id}/messages`  | autenticado         | Log de mensagens recebidas (aceitas e recusadas)   |

**Implementado na ETAPA 8.** Filtros de `GET /instruments`: `q` (código, nome,
local ou número de série), `status` e `instrument_type`; `sort` aceita `code`,
`name`, `status`, `calibration_due_date` e `last_communication_at`. Cada
equipamento traz dois campos calculados:

- `calibration_valid`: a calibração vale até `calibration_due_date`, inclusive
  (data em UTC). Sem data registrada, não é válida.
- `online`: houve comunicação (heartbeat, worklist ou resultado) nos últimos
  5 minutos.

O cadastro exige `code`, `name`, `instrument_type` e `calibration_due_date`. O
código é normalizado para maiúsculas e, junto com o tipo, não pode ser alterado
depois: identifica o equipamento nos resultados já gravados. Código ou número de
série repetidos retornam `409 DUPLICATED_INSTRUMENT`. `PATCH` recusa `null` em
`name`, `status` e `calibration_due_date`; alterações são auditadas
(`INSTRUMENT_UPDATED`) apenas com os campos que mudaram.

A resposta do cadastro e da rotação inclui `api_key` (`lt_inst_...`). A chave é
exibida **somente** nessa resposta: o banco guarda apenas o SHA-256 dela, e o
audit trail não registra nem a chave nem o hash. A rotação aceita um `reason`
opcional (`INSTRUMENT_KEY_ROTATED`) e invalida a chave anterior no mesmo commit.

`GET /instruments/{id}/messages` é paginado (mais recentes primeiro), aceita
`status=ACCEPTED|REJECTED` e devolve o `payload` exatamente como foi recebido,
com código e mensagem da recusa ou o `test_result_id` gerado.

### Instrumentos: integração (header `X-Instrument-Key`)
| Método | Rota                     | Descrição                                                          |
| ------ | ------------------------ | ------------------------------------------------------------------ |
| GET    | `/instruments/worklist`  | Testes pendentes compatíveis com o tipo do instrumento             |
| POST   | `/instruments/results`   | Envia um resultado                                                 |
| POST   | `/instruments/heartbeat` | Sinaliza que o equipamento está conectado                          |

Chave ausente, desconhecida ou revogada retorna `401 INVALID_INSTRUMENT_KEY`. O
JWT de um usuário não autentica um instrumento, e a chave de um instrumento não
dá acesso às rotas de usuário. Como não há equipamento a quem atribuir a
tentativa, ela vai para o log da aplicação, e não para o log de mensagens.

**Worklist.** Retorna os testes `PENDING` de amostras `IN_ANALYSIS` cujo tipo de
teste exige o tipo do equipamento, ordenados por prioridade (`URGENT` →
`LOW`), recebimento e ID. `limit` vai de 1 a 100 (padrão 50). Cada item traz
`sample_code`, `priority`, `received_at`, `test`, `test_name`, `unit`,
`spec_min`, `spec_max`, `decimal_places` e `assigned_at`. Equipamento
inativo, em manutenção ou com calibração vencida recebe `409` com o código
correspondente; mesmo assim a comunicação é registrada.

**Heartbeat.** O corpo é opcional (`{"instrument_id": "PH-METER-01"}`); se
enviado, precisa ser o dono da chave. Funciona também para equipamentos parados e
responde `status`, `calibration_due_date`, `calibration_valid`, `can_measure` e
`server_time`.

Exemplo de envio:

```http
POST /api/v1/instruments/results
X-Instrument-Key: lt_inst_9f2c...
Content-Type: application/json

{
  "instrument_id": "PH-METER-01",
  "sample_code": "SMP-2026-0001",
  "test": "PH",
  "result": "7.21",
  "unit": "pH"
}
```

```json
201 Created
{
  "message_id": 318,
  "status": "ACCEPTED",
  "result_id": 912,
  "sample_code": "SMP-2026-0001",
  "test": "PH",
  "result": "7.21",
  "unit": "pH",
  "spec_status": "IN_SPEC",
  "spec_min": "6.5000",
  "spec_max": "7.5000"
}
```

`result` aceita número ou texto, com até 14 dígitos e 4 casas decimais. Códigos
de amostra e de teste são normalizados para maiúsculas; a unidade é comparada
exatamente (`mS` ≠ `ms`). Campos extras são recusados. O resultado aceito é
gravado com `source = INSTRUMENT`, sem `entered_by`, e auditado como
`RESULT_ENTERED` pelo próprio equipamento (`actor_type = INSTRUMENT`). O
resultado, a mensagem `ACCEPTED` e a auditoria são gravados na mesma transação.
Um resultado de instrumento não impede a aprovação pelo revisor: o princípio
dos quatro olhos considera apenas os usuários que lançaram resultados.

Rejeições possíveis, na ordem em que são verificadas. A mensagem é gravada como
`REJECTED` com o código, auditada como `INSTRUMENT_MESSAGE_REJECTED` (vinculada à
timeline da amostra quando o código existe) e nenhum resultado é gravado. O
envelope de erro traz `details.message_id`:

| Código                      | HTTP | Situação                                                   |
| --------------------------- | ---- | ---------------------------------------------------------- |
| `INVALID_PAYLOAD`           | 422  | Corpo ausente, não é objeto, campo ausente/extra ou valor inválido (`details.errors`) |
| `INSTRUMENT_ID_MISMATCH`    | 403  | `instrument_id` do corpo difere do dono da chave (RN-19)   |
| `INSTRUMENT_NOT_ACTIVE`     | 409  | Equipamento em manutenção ou inativo (RN-20)               |
| `CALIBRATION_EXPIRED`       | 409  | Calibração vencida ou não registrada (RN-20)               |
| `SAMPLE_NOT_FOUND`          | 404  | Código de amostra inexistente                              |
| `SAMPLE_NOT_IN_ANALYSIS`    | 409  | Amostra não está em análise (RN-22)                        |
| `TEST_NOT_ASSIGNED`         | 409  | Teste não atribuído à amostra                              |
| `SAMPLE_TEST_CANCELLED`     | 409  | Teste atribuído, mas cancelado                             |
| `INSTRUMENT_TYPE_MISMATCH`  | 409  | Tipo do equipamento incompatível com o teste (RN-21)       |
| `TEST_ALREADY_COMPLETED`    | 409  | Teste já tem resultado; correção só manual, com justificativa (RN-22) |
| `UNIT_MISMATCH`             | 422  | Unidade diferente da especificada (RN-23)                  |

Envios simultâneos para o mesmo teste são serializados: no PostgreSQL a amostra
é bloqueada (`SELECT ... FOR UPDATE`) durante a validação e, como última
defesa, o índice único de versão vigente impede duas gravações. O segundo envio
é recusado como `TEST_ALREADY_COMPLETED` e também fica no log. JSON sintaticamente
inválido é recusado pelo framework (`422 VALIDATION_ERROR`) antes da integração
e não entra no log, pois não há conteúdo a registrar.

### Audit trail
| Método | Rota                 | Permissão    | Descrição                                                                  |
| ------ | -------------------- | ------------ | -------------------------------------------------------------------------- |
| GET    | `/audit-logs`        | `AUDIT_READ` | Consulta paginada (usuário, ação, entidade, amostra, período)              |
| GET    | `/audit-logs/verify` | `AUDIT_READ` | Verifica a cadeia de hashes e aponta o primeiro registro adulterado        |

Não existem rotas `POST`, `PUT`, `PATCH` ou `DELETE` para o audit trail. Os
registros são criados apenas pelos serviços, como efeito das operações.

**Consulta implementada na ETAPA 7.** Filtros de `GET /audit-logs`:
`user_id`, `instrument_id`, `actor_type` (`USER`, `INSTRUMENT`, `SYSTEM`),
`action`, `entity_type`, `entity_id`, `sample_id`, `occurred_from`, `occurred_to`.
Os filtros são combinados por AND; entidades e ações usam correspondência exata.
As datas são inclusivas e normalizadas para UTC; datas sem fuso são interpretadas
como UTC. Período invertido retorna `422 INVALID_DATE_RANGE`.

A paginação usa `page` e `size` (máximo 100). `sort` aceita `occurred_at`,
`action` ou `id`, com `-` para ordem decrescente; o padrão é `-occurred_at`,
com desempate por ID. A resposta inclui o nome do ator registrado no momento
da ação, valores anterior/novo, justificativa, correlação e hashes.

`GET /audit-logs/verify` verifica **toda** a cadeia por ID, sem filtros nem
paginação. Usa leitura em lotes numa única consulta, sem bloquear os escritores
da auditoria. Retorna HTTP 200 também quando encontra inconsistência:

```json
{
  "valid": false,
  "checked_records": 12,
  "first_invalid_id": 15,
  "error_code": "RECORD_HASH_MISMATCH"
}
```

`checked_records` inclui o registro inválido. `RECORD_HASH_MISMATCH` indica
divergência entre conteúdo e hash; `PREVIOUS_HASH_MISMATCH` indica quebra do
encadeamento. Na cadeia válida, `first_invalid_id` e `error_code` são nulos.
Uma cadeia vazia é válida e verifica zero registros. Lacunas nos IDs não são
falhas, pois uma transação revertida pode consumir um ID.

A verificação detecta alterações de conteúdo e quebras de encadeamento; não
detecta remoção da cauda nem recálculo completo da cadeia sem uma referência
externa confiável. Ela não substitui o trigger append-only e não é certificação
de conformidade regulatória.

### Sample Timeline

`GET /samples/{id}/timeline` exige `SAMPLE_READ` (inclui o analista), retorna
o envelope paginado comum e aceita `page` e `size` (máximo 100). A ordem é
sempre cronológica por `occurred_at`, com desempate por ID. Amostra inexistente
retorna `404 SAMPLE_NOT_FOUND`.

Cada evento vem de `audit_logs.sample_id`: `id`, `occurred_at` em UTC,
`actor_type`, `actor_name`, `user_id`, `instrument_id`, `action`, identificação
da entidade, `sample_id`, `old_value`, `new_value` e `reason`.
Não inclui IP, request ID ou hashes internos da consulta administrativa.

- `is_correction`: verdadeiro em eventos `RESULT_AMENDED`.
- `has_oos`: verdadeiro se o valor anterior **ou** o novo do evento contém
  `spec_status=OOS`. Uma correção para `IN_SPEC` continua destacando seu OOS
  anterior; o indicador é do evento, não do estado atual da amostra.

Consultar auditoria, verificar a cadeia e ler a timeline não cria novos eventos.
A apresentação visual da timeline será implementada no frontend da ETAPA 9.

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
