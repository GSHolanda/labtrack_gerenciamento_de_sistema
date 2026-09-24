# LabTrack — Laboratory Sample Management System

**Mini-LIMS** que acompanha o ciclo de vida completo de uma amostra de
laboratório, do recebimento à aprovação ou reprovação, com rastreabilidade
total, regras de negócio de um ambiente regulado, integração com instrumentos
e audit trail imutável.

> 🚧 **Em desenvolvimento.** O projeto é construído em 14 etapas incrementais.
> Veja o [plano de implementação](docs/roadmap.md). Etapa atual: **12 de 14 concluídas**.

---

## O problema

Laboratórios de controle de qualidade processam centenas de amostras. Sem um
sistema dedicado, os dados ficam espalhados em planilhas e cadernos, e fica
difícil responder perguntas básicas:

- Em que etapa está a amostra do lote X?
- Quem inseriu este resultado, quando, e ele foi alterado?
- Algum resultado ficou fora da especificação? Quem aprovou mesmo assim?
- O valor veio do equipamento ou foi digitado?

## A solução

O LabTrack centraliza o processo em um workflow controlado:

```
Recebida → Testes atribuídos → Em análise → Resultados → Aguardando revisão → Aprovada / Reprovada
```

- **Workflow com máquina de estados**: nenhuma etapa é pulada. Não se aprova
  amostra com teste pendente, com resultado fora da especificação ou revisada
  pela mesma pessoa que gerou os resultados.
- **Avaliação automática de especificação**: todo resultado é comparado aos
  limites e classificado como *dentro da especificação* ou **OOS**.
- **Resultados versionados**: correções criam nova versão com justificativa.
  O valor original nunca é perdido.
- **Audit trail imutável**: quem, quando, o quê, valor anterior e novo, com
  cadeia de hashes para detectar adulteração.
- **Integração com instrumentos**: equipamentos enviam resultados por API REST
  autenticada. Um simulador separado demonstra a integração.
- **Controle de acesso por perfil**: Administrador, Analista, Revisor e Gestor.
- **Dashboard, Sample Timeline e relatório em PDF.**

## Stack

| Camada          | Tecnologia                                     |
| --------------- | ---------------------------------------------- |
| Frontend        | React 19, TypeScript, Vite                     |
| Backend         | Python 3.11+, FastAPI, Pydantic v2             |
| Persistência    | PostgreSQL, SQLAlchemy 2.0, Alembic            |
| Segurança       | JWT, RBAC por permissões, chave de API por instrumento |
| Qualidade       | pytest, Ruff, oxlint, testes de arquitetura    |
| Infraestrutura  | Docker, Docker Compose, Nginx                  |

## Estrutura do repositório

```
labtrack/
├── backend/                 # API REST (FastAPI) em camadas
│   ├── app/
│   │   ├── api/             #   HTTP: rotas, autenticação, erros
│   │   ├── services/        #   Casos de uso e regras de negócio
│   │   ├── domain/          #   Regras puras: workflow, OOS, permissões
│   │   ├── repositories/    #   Acesso a dados
│   │   ├── models/          #   ORM SQLAlchemy
│   │   ├── schemas/         #   Contratos da API (Pydantic)
│   │   ├── database/        #   Engine, sessão, base declarativa
│   │   └── core/            #   Configuração, logs, segurança
│   └── tests/               #   Testes unitários, de API e de arquitetura
├── frontend/                # Cliente web React + TypeScript
├── instrument-simulator/    # Simulador de equipamentos (processo separado)
└── docs/                    # Arquitetura, modelo de dados, API, fluxo, roadmap
```

## Documentação

| Documento                                        | Conteúdo                                                        |
| ------------------------------------------------ | --------------------------------------------------------------- |
| [Arquitetura](docs/architecture.md)              | Camadas, regra de dependência, decisões técnicas, troca de tecnologia |
| [Modelo de dados](docs/database.md)              | Diagrama ER, dicionário de dados, constraints e índices         |
| [API](docs/api.md)                               | Endpoints, matriz de permissões, integração com instrumentos    |
| [Ciclo da amostra](docs/sample-lifecycle.md)     | Máquina de estados, regras de negócio (RN-01 a RN-28), timeline |
| [Testes](docs/testing.md)                        | Camadas de teste, CI, cobertura e matriz regra → teste          |
| [Plano de implementação](docs/roadmap.md)        | As 14 etapas e o status de cada uma                             |

## Como executar (estado atual)

A API já oferece autenticação, cadastros, amostras, testes atribuídos,
resultados manuais e revisão completa. A ETAPA 6 inclui avaliação OOS com
`Decimal`, correções versionadas com justificativa, histórico OOS preservado
e aprovação com senha e segregação de funções. Resultados ficam bloqueados
após o envio para revisão; o revisor pode devolver a amostra para análise
com justificativa.

A ETAPA 7 adiciona consulta paginada do audit trail, verificação da cadeia de
hashes e endpoint da Sample Timeline, com histórico de correções e OOS.
As consultas administrativas exigem `AUDIT_READ`; a timeline exige `SAMPLE_READ`.
Veja filtros, respostas e limites da verificação na [documentação da API](docs/api.md).

A ETAPA 8 adiciona a gestão de equipamentos (chave de integração exibida uma
única vez e guardada só como hash, rotação, log de mensagens), a integração
REST (`worklist`, `results`, `heartbeat`) com as regras RN-19 a RN-24, o
simulador de instrumentos em `instrument-simulator/` e os dados de
demonstração, gerados pelos próprios serviços com histórico coerente.

A ETAPA 9 entrega o frontend: login, menu e rotas por perfil, amostras (lista,
registro, detalhe com as ações do workflow, resultados, correções e Sample
Timeline visual), resultados com filtro OOS, catálogo de testes, equipamentos
com chave exibida uma única vez, audit trail com verificação de integridade,
administração e um dashboard básico. Veja o [README do frontend](frontend/README.md).

A ETAPA 10 entrega o dashboard: carga de trabalho atual, indicadores do período
com comparação ao período anterior (aprovadas, reprovadas, taxa de aprovação,
tempo até a decisão, resultados OOS) e gráficos de decisões, taxa de aprovação,
status e OOS por teste, agrupados no fuso do laboratório.

A ETAPA 11 entrega o relatório de análise das amostras aprovadas ou reprovadas:
prévia na interface e PDF com identificação, resultados, histórico de correções
(inclusive OOS), testes cancelados e parecer da revisão. Cada emissão fica no
audit trail com a impressão digital SHA-256 impressa no rodapé do documento.

A ETAPA 12 consolida os testes: fluxo ponta a ponta, cenários negativos de
todas as regras de negócio com rastreabilidade regra → teste, a suíte inteira
também no PostgreSQL, cobertura mínima e integração contínua no GitHub Actions.
Veja a [estratégia de testes](docs/testing.md).

A próxima entrega empacota tudo em contêineres (ETAPA 13).

**Backend**

```bash
docker compose up -d db            # PostgreSQL
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head               # cria as tabelas e os perfis
python -m app.cli create-admin     # cria o usuário 'admin' (pede a senha)
uvicorn app.main:app --reload      # http://localhost:8000/docs
pytest                             # testes
```

**Dados de demonstração e simulador de instrumentos**

Num banco recém-migrado, gere 20 amostras em todas as etapas do fluxo, com
5 produtos, 4 clientes, 5 usuários, 6 equipamentos e 8 tipos de teste. O
histórico cobre as últimas semanas e é produzido pelos mesmos serviços da API.
A senha de todos os usuários é `Demo@2026` (ou `LABTRACK_DEMO_PASSWORD`).
Se o `admin` já existir, a senha dele não muda.

```bash
cd backend
python -m app.cli seed-demo --simulator-config ../instrument-simulator/config.json

cd ../instrument-simulator
pip install -e ".[dev]"
python -m simulator worklist           # testes pendentes por equipamento
python -m simulator run --once         # mede e envia os resultados pela API
```

Veja as opções no [README do simulador](instrument-simulator/README.md).

**Frontend**

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173 (usa a API em :8000)
npm test                           # testes (Vitest)
```

Com os dados de demonstração, entre como `carlos.silva` (analista),
`ana.souza` (revisora), `marcos.lima` (gestor) ou `admin`, senha `Demo@2026`.

A execução completa com `docker compose up` chega na ETAPA 13.

## Integridade de dados

O LabTrack aplica boas práticas de rastreabilidade e integridade de dados
comuns em sistemas laboratoriais. **Não há alegação de conformidade oficial
com normas ou regulamentações.** É um projeto de portfólio que demonstra os
conceitos.

Este é um projeto autoral e independente. Não reproduz código, layout ou
funcionalidades proprietárias de nenhum produto LIMS comercial.
