import { useQuery } from '@tanstack/react-query'

import { clientsApi, productsApi, testDefinitionsApi } from '../api/masterData'
import { queryKeys } from '../api/queryKeys'

// Listas usadas em filtros e formulários. O limite da API é 100 itens por página,
// suficiente para cadastros de um laboratório; mudam pouco, então ficam em cache.
const REFERENCE = { page: 1, size: 100, sort: 'name' }
const STALE = 5 * 60 * 1000

export function useProducts(activeOnly = false) {
  const filters = { ...REFERENCE, is_active: activeOnly ? true : undefined }
  return useQuery({
    queryKey: queryKeys.products(filters),
    queryFn: () => productsApi.search(filters),
    select: (page) => page.items,
    staleTime: STALE,
  })
}

export function useClients(activeOnly = false) {
  const filters = { ...REFERENCE, is_active: activeOnly ? true : undefined }
  return useQuery({
    queryKey: queryKeys.clients(filters),
    queryFn: () => clientsApi.search(filters),
    select: (page) => page.items,
    staleTime: STALE,
  })
}

export function useTestDefinitions(activeOnly = false) {
  const filters = { ...REFERENCE, is_active: activeOnly ? true : undefined }
  return useQuery({
    queryKey: queryKeys.testDefinitions(filters),
    queryFn: () => testDefinitionsApi.search(filters),
    select: (page) => page.items,
    staleTime: STALE,
  })
}
