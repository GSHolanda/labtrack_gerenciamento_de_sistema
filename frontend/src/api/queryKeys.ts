// Chaves de cache do TanStack Query, centralizadas para invalidar de forma consistente.

export const queryKeys = {
  samples: ['samples'] as const,
  sampleList: (filters: object) => ['samples', 'list', filters] as const,
  sample: (id: number) => ['samples', 'detail', id] as const,
  timeline: (id: number) => ['samples', 'timeline', id] as const,
  results: ['results'] as const,
  resultList: (filters: object) => ['results', 'list', filters] as const,
  resultHistory: (sampleTestId: number) => ['results', 'history', sampleTestId] as const,
  clients: (filters: object) => ['clients', filters] as const,
  products: (filters: object) => ['products', filters] as const,
  specifications: (productId: number) => ['products', 'specifications', productId] as const,
  testDefinitions: (filters: object) => ['test-definitions', filters] as const,
  instruments: ['instruments'] as const,
  instrumentList: (filters: object) => ['instruments', 'list', filters] as const,
  instrument: (id: number) => ['instruments', 'detail', id] as const,
  instrumentMessages: (id: number, filters: object) =>
    ['instruments', 'messages', id, filters] as const,
  audit: (filters: object) => ['audit', filters] as const,
  users: (filters: object) => ['users', filters] as const,
  roles: ['roles'] as const,
  dashboard: ['dashboard'] as const,
  dashboardSummary: (days: number) => ['dashboard', 'summary', days] as const,
  dashboardCharts: (days: number) => ['dashboard', 'charts', days] as const,
  sampleReport: (sampleId: number) => ['reports', 'sample', sampleId] as const,
}
