import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router'

/**
 * Filtros, página e ordenação de uma listagem guardados na URL: a tela pode ser
 * recarregada, compartilhada e navegada pelo histórico sem perder o contexto.
 */
export function useListParams() {
  const [params, setParams] = useSearchParams()

  const get = useCallback((key: string) => params.get(key) ?? '', [params])
  const getAll = useCallback((key: string) => params.getAll(key), [params])

  const update = useCallback(
    (changes: Record<string, string | string[] | null | undefined>, resetPage = true) => {
      setParams(
        (current) => {
          const next = new URLSearchParams(current)
          for (const [key, value] of Object.entries(changes)) {
            next.delete(key)
            if (Array.isArray(value)) value.forEach((item) => next.append(key, item))
            else if (value) next.set(key, value)
          }
          if (resetPage && !('page' in changes)) next.delete('page')
          return next
        },
        { replace: true },
      )
    },
    [setParams],
  )

  const page = Math.max(Number(params.get('page')) || 1, 1)
  const sort = params.get('sort') ?? undefined

  return useMemo(
    () => ({
      params,
      get,
      getAll,
      update,
      page,
      sort,
      setPage: (value: number) => update({ page: value > 1 ? String(value) : null }, false),
      setSort: (value: string) => update({ sort: value }),
      clear: () => setParams(new URLSearchParams(), { replace: true }),
    }),
    [params, get, getAll, update, page, sort, setParams],
  )
}

export function toNumber(value: string): number | undefined {
  const parsed = Number(value)
  return value && Number.isFinite(parsed) ? parsed : undefined
}
