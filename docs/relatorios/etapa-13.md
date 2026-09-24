# Relatório da ETAPA 13: Docker

**Status:** concluída · **Branch:** `claude/festive-bell-x898pg`

## Resumo

O LabTrack sobe inteiro com um comando: `docker compose up --build` cria o
banco, aplica as migrações, gera a demonstração, inicia a API, publica a
interface pelo Nginx em http://localhost:8080 e coloca o simulador de
instrumentos para enviar resultados pela API REST.

## Entregas

| Item | Resultado |
| ---- | --------- |
| Imagem da API | *Multi-stage*: dependências em camada própria, virtualenv copiado para `python:3.11-slim`, usuário sem root (UID 10001), healthcheck que inclui o banco |
| Imagem da interface | *Multi-stage*: build do Vite no Node 22, servido pelo Nginx 1.28 com rotas da SPA, cache dos arquivos com hash, cabeçalhos de segurança e proxy de `/api` e `/docs` |
| Imagem do simulador | Pacote Python mínimo, mesmo UID para ler as chaves geradas |
| Compose | `db` → `migrate` (tarefa única) → `api` → `frontend` e `simulator`, com condições de saúde e conclusão; volumes do banco e das chaves |
| Idempotência | `seed-demo --if-empty`: a demonstração só é gerada na primeira subida; nas seguintes, nada muda |
| Segurança | A API recusa a chave JWT de desenvolvimento em produção; API sem porta publicada; IP do cliente preservado no audit trail via `X-Forwarded-For` |
| Smoke test | `scripts/smoke_test.py`: 16 verificações pela porta publicada (SPA, cabeçalhos, API pronta, Swagger, login, amostras, PDF com impressão digital, cadeia do audit trail, resultados do simulador) |
| CI | Job **Docker**: build, subida com `--wait`, smoke test, segunda subida com dados preservados e novo smoke test |
| Documentação | [`docs/deployment.md`](../deployment.md) (serviços, imagens, variáveis, caminho para produção), `.env.example` na raiz, README com execução rápida |

## Validação

- Stack completa com `docker compose up --wait`: todos os serviços saudáveis,
  migrações e demonstração aplicadas (20 amostras, 6 equipamentos).
- Smoke test aprovado na primeira subida e depois de `down` + `up` (dados
  preservados, mensagem "Demonstração já gerada anteriormente").
- Simulador em contêiner: mediu a worklist, enviou resultados (inclusive OOS) e
  foi recusado onde deveria (equipamento em manutenção e calibração vencida).
- Interface Dockerizada no Chromium: usuários de demonstração no login,
  dashboard, equipamentos online, emissão do PDF e recarga de rota profunda,
  sem erros de console.
- Audit trail registrou o IP do cliente (gateway do Docker), e não o do Nginx.
- Suítes: backend 469 em SQLite (96,9% de cobertura) e 475 no PostgreSQL,
  simulador 41 e frontend 94.
- No GitHub, a [execução do CI](https://github.com/GSHolanda/labtrack_gerenciamento_de_sistema/actions/runs/35954681259)
  do commit `d4d167f` passou nos cinco jobs, inclusive o **Docker**: build com
  as imagens oficiais do Docker Hub, stack completa, smoke test, segunda subida
  com dados preservados e novo smoke test.

## Problemas encontrados

- **Docker Hub com limite de requisições (429)** neste ambiente de nuvem: as
  imagens base vieram de um espelho (`mirror.gcr.io`) só para o teste local.
  Os Dockerfiles do repositório usam as imagens oficiais.
- **Proxy com inspeção de TLS** neste ambiente: o build local usou variantes
  temporárias dos Dockerfiles (fora do repositório) com o certificado do proxy.
  Uma delas deixou a variável de proxy na imagem do simulador, que não conseguia
  falar com a API; o problema era só do ensaio local e foi corrigido
  reconstruindo a variante.
- A mensagem da segunda subida repetia "gere a demonstração em um banco novo",
  o que confundia; ficou só "Demonstração já gerada anteriormente; nada foi
  alterado."
- `init-test-db.sql` fixava o dono `labtrack`; agora o banco de testes pertence
  a quem o cria, e o compose funciona com outro `POSTGRES_USER`.

## Decisões

- A API não publica porta: tudo passa pelo Nginx (uma origem, sem CORS), e o
  simulador usa a rede interna, como um equipamento no laboratório.
- Migrações e demonstração num serviço de tarefa única, não no *entrypoint* da
  API: uma réplica extra da API nunca tenta migrar ao mesmo tempo.
- O padrão do compose é a demonstração. O caminho para produção está documentado
  e é imposto pela própria API: a chave de desenvolvimento é recusada.

## Próxima etapa

ETAPA 14: documentação final e apresentação (README com capturas de tela,
diagramas, roteiro de apresentação e perguntas prováveis de entrevista).
