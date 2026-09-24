import { QueryClient } from '@tanstack/react-query'

import { ApiError } from '../api/client'

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        refetchOnWindowFocus: true,
        // Erros do cliente (4xx) não melhoram com nova tentativa; falhas de rede sim.
        retry: (failures, error) =>
          failures < 2 && !(error instanceof ApiError && error.status >= 400 && error.status < 500),
      },
    },
  })
}
