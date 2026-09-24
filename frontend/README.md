# LabTrack — Frontend

Cliente web do LabTrack em **React 19 + TypeScript** (Vite), com React Router,
TanStack Query e ícones Lucide. Toda a regra de negócio fica no backend: a
interface mostra o que o perfil pode fazer, mas quem autoriza é sempre a API.

## Telas

| Menu           | Rota                   | Quem vê                        | O que faz |
| -------------- | ---------------------- | ------------------------------ | --------- |
| Dashboard      | `/dashboard`           | todos                          | Contagem por status (atalhos para a lista filtrada), resultados OOS vigentes e fila do perfil (revisão para o revisor, amostras sob responsabilidade para o analista). Os KPIs e gráficos completos chegam na ETAPA 10. |
| Amostras       | `/samples`             | `SAMPLE_READ`                  | Pesquisa com filtros na URL, ordenação, progresso dos testes e alerta OOS; registro de amostra com prévia do plano analítico. |
|                | `/samples/:id`         | `SAMPLE_READ`                  | Dados da amostra, ações do workflow conforme status e permissão, testes com especificação, resultado vigente, origem (usuário ou equipamento), histórico de versões, lançamento e correção, atribuição e cancelamento de testes, e a **Sample Timeline** visual. |
| Testes         | `/tests`               | todos                          | Catálogo de tipos de teste; o administrador cria e altera. |
| Resultados     | `/results`             | `SAMPLE_READ`                  | Pesquisa de resultados vigentes e corrigidos, com filtro OOS. |
| Equipamentos   | `/instruments`         | todos                          | Status, calibração e comunicação (atualizados a cada 30 s); cadastro com a chave exibida uma única vez. |
|                | `/instruments/:id`     | todos                          | Cadastro, rotação de chave e log de mensagens aceitas e recusadas, com o payload original. |
| Audit Trail    | `/audit`               | `AUDIT_READ`                   | Consulta com filtros, detalhes com hashes e verificação de integridade da cadeia. |
| Relatórios     | `/reports`             | `REPORT_EXPORT`                | Amostras finalizadas; o PDF chega na ETAPA 11. |
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

Os testes renderizam a aplicação real (rotas, autenticação e providers) com o
`fetch` simulado: login e retorno à página pedida, sessão expirada, menu e
rotas por perfil, ações do workflow por status e permissão, aprovação com
senha, prévia OOS no lançamento, justificativa obrigatória na correção,
formatação de decimais e datas, e o texto da timeline.
