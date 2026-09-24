# LabTrack — Frontend

Cliente web do LabTrack em **React 19 + TypeScript** (Vite), com React Router,
TanStack Query e ícones Lucide. Toda a regra de negócio fica no backend: a
interface mostra o que o perfil pode fazer, mas quem autoriza é sempre a API.

## Telas

| Menu           | Rota                   | Quem vê                        | O que faz |
| -------------- | ---------------------- | ------------------------------ | --------- |
| Dashboard      | `/dashboard`           | todos                          | Carga atual (em aberto, em análise, em revisão, com OOS vigente, urgentes), filtro de período (7/30/90 dias, 12 meses) que vale para tudo abaixo dele, indicadores com variação contra o período anterior, gráficos de decisões, taxa de aprovação, status e OOS por teste (cada um com tabela equivalente) e a fila do perfil. |
| Amostras       | `/samples`             | `SAMPLE_READ`                  | Pesquisa com filtros na URL, ordenação, progresso dos testes e alerta OOS; registro de amostra com prévia do plano analítico. |
|                | `/samples/:id`         | `SAMPLE_READ`                  | Dados da amostra, ações do workflow conforme status e permissão, testes com especificação, resultado vigente, origem (usuário ou equipamento), histórico de versões, lançamento e correção, atribuição e cancelamento de testes, e a **Sample Timeline** visual. |
| Testes         | `/tests`               | todos                          | Catálogo de tipos de teste; o administrador cria e altera. |
| Resultados     | `/results`             | `SAMPLE_READ`                  | Pesquisa de resultados vigentes e corrigidos, com filtro OOS. |
| Equipamentos   | `/instruments`         | todos                          | Status, calibração e comunicação (atualizados a cada 30 s); cadastro com a chave exibida uma única vez. |
|                | `/instruments/:id`     | todos                          | Cadastro, rotação de chave e log de mensagens aceitas e recusadas, com o payload original. |
| Audit Trail    | `/audit`               | `AUDIT_READ`                   | Consulta com filtros, detalhes com hashes e verificação de integridade da cadeia. |
| Relatórios     | `/reports`             | `REPORT_EXPORT`                | Amostras aprovadas ou reprovadas, com prévia e emissão do PDF por linha. |
|                | `/reports/:id`         | `REPORT_EXPORT`                | Prévia do relatório com o mesmo conteúdo e fuso do PDF, emissão com download e confirmação da impressão digital. |
| Administração  | `/admin`               | `USER_MANAGE` ou `MASTER_DATA_MANAGE` | Usuários, clientes, produtos e editor do plano analítico. |

O menu e a proteção das rotas usam a mesma configuração
(`src/layouts/navigation.ts`): um item só aparece para quem pode abri-lo, e o
acesso direto a uma rota sem permissão mostra "Acesso negado".

## Estrutura

```
src/
├── app/          # App, rotas (protegidas por permissão), Root com providers, QueryClient
├── api/          # Cliente HTTP (token, envelope de erro, 401) e funções por recurso
├── components/   # UI reutilizável: Button, Badge, Modal, Field, Pagination, Toaster...
├── features/     # Um módulo por item do menu (páginas, diálogos e regras de exibição)
│   ├── auth/     #   sessão, provedor, guardas de rota, login
│   ├── samples/  #   lista, cadastro, detalhe, ações, resultados, timeline
│   └── ...       #   dashboard, results, tests, instruments, audit, reports, admin
├── hooks/        # Filtros na URL, debounce, dados de referência (produtos, clientes, testes)
├── layouts/      # Menu lateral, barra superior (telas pequenas) e navegação
├── lib/          # Formatação pt-BR (datas, decimais exatos) e rótulos dos códigos da API
├── styles/       # Tokens de design, base, layout, componentes e telas
├── test/         # Setup do Vitest, fixtures e utilitários (API simulada, app real)
└── types/        # Tipos espelhando os contratos da API
```

## Decisões

- **Sessão**: o JWT fica no `sessionStorage` (sobrevive a recarregar a página,
  termina ao fechar a aba) e é validado com `GET /auth/me` ao abrir o app, o
  que também atualiza as permissões. Um `401` numa requisição autenticada, ou o
  horário de expiração do token, encerra a sessão e volta ao login com aviso,
  retornando depois à tela pedida. Uma saída voluntária não guarda a tela de
  origem para o próximo usuário.
- **Estado do servidor** com TanStack Query: cada operação atualiza o detalhe
  da amostra com a resposta da API e invalida listas, timeline e dashboard.
- **Filtros na URL**: listas podem ser recarregadas, compartilhadas e navegadas
  pelo histórico sem perder filtros, página e ordenação.
- **Decimais como texto**: valores analíticos chegam como texto (`"7.2100"`) e
  são exibidos sem conversão para `float` e sem esconder dígitos registrados
  (`7,2150` com 2 casas continua `7,215`). A entrada aceita vírgula ou ponto.
  A prévia "dentro/fora da especificação" no lançamento compara com `BigInt`;
  a classificação oficial é sempre a do servidor.
- **Datas**: a API trabalha em UTC; a interface mostra no fuso do navegador.
- **Sem biblioteca de componentes**: CSS próprio com tokens, para manter o
  bundle pequeno e o visual consistente.
- **Gráficos** (Recharts, carregado só ao abrir o dashboard): nenhum eixo duplo;
  série única sem legenda e duas séries com legenda; colunas de até 24px com
  ponta arredondada e 2px de espaço entre segmentos; linhas de 2px; grade
  discreta. Cores da paleta de referência validadas contra a superfície branca
  (azul × laranja passa; verde × vermelho foi reprovado para daltonismo). O
  vermelho de status aparece só em OOS, sempre com ícone e rótulo. Todo gráfico
  tem tooltip (mouse e teclado) e tabela com os mesmos valores. Variações usam
  seta e texto ("piora"/"melhora" para leitores de tela), não só cor.
- **Relatórios**: a prévia vem do JSON (sem auditoria) e a emissão baixa o PDF
  com a mesma autenticação do resto da API (`http.download`). Depois da
  emissão, timeline e audit trail são atualizados e a interface compara a
  impressão digital do PDF (`X-Report-SHA256`) com a da prévia.

## Executando

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxy /api -> http://localhost:8000)
```

Com a API rodando e os dados de demonstração gerados
(`python -m app.cli seed-demo`), a tela de login lista os usuários de
demonstração (senha `Demo@2026`) em modo de desenvolvimento, ou quando
`VITE_DEMO_MODE=true`.

| Script               | Descrição                                   |
| -------------------- | ------------------------------------------- |
| `npm run dev`        | Servidor de desenvolvimento com HMR         |
| `npm run build`      | Checagem de tipos + build de produção       |
| `npm run typecheck`  | Somente checagem de tipos                   |
| `npm run lint`       | Lint (oxlint)                               |
| `npm test`           | Testes (Vitest + Testing Library, jsdom)    |
| `npm run test:coverage` | Testes com cobertura (piso de 75% das linhas) |

Os testes renderizam a aplicação real (rotas, autenticação e providers) com o
`fetch` simulado: login e retorno à página pedida, sessão expirada, menu e
rotas por perfil, ações do workflow por status e permissão, aprovação com
senha, prévia OOS no lançamento, justificativa obrigatória na correção,
formatação de decimais e datas, o texto da timeline, a prévia, emissão e
download do relatório, e as telas de audit trail (verificação da cadeia),
resultados, catálogo de testes, equipamentos (chave exibida uma vez, rotação,
log) e administração (usuários, clientes, plano analítico).
