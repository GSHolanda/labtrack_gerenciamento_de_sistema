# LabTrack — Frontend

Cliente web do LabTrack em **React + TypeScript** (Vite).

## Estrutura

```
src/
├── app/          # Shell da aplicação: App, rotas, providers (auth, query client)
├── api/          # Cliente HTTP e funções por recurso (samples, results, instruments...)
├── components/   # Componentes de UI reutilizáveis (DataTable, StatusBadge, Card, PageHeader)
├── features/     # Módulos funcionais, um por item do menu:
│                 #   auth, dashboard, samples, tests, results, instruments,
│                 #   audit, reports, admin (cada um com páginas, hooks e componentes próprios)
├── hooks/        # Hooks compartilhados (useAuth, usePagination, useDebounce)
├── layouts/      # Layout autenticado: menu lateral + barra superior
├── lib/          # Utilitários (formatação de datas/números, permissões)
├── types/        # Tipos do domínio, espelhando os contratos da API
└── styles/       # Tokens de design e estilos globais
```

A organização por **feature** mantém cada módulo coeso (páginas, hooks e
componentes daquele domínio no mesmo lugar). A comunicação com o backend fica
isolada em `api/`, então trocar o cliente HTTP ou gerar o cliente a partir do
OpenAPI não afeta as telas.

## Executando

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxy /api -> http://localhost:8000)
```

| Script              | Descrição                               |
| ------------------- | --------------------------------------- |
| `npm run dev`       | Servidor de desenvolvimento com HMR     |
| `npm run build`     | Checagem de tipos + build de produção   |
| `npm run typecheck` | Somente checagem de tipos               |
| `npm run lint`      | Lint (oxlint)                           |
