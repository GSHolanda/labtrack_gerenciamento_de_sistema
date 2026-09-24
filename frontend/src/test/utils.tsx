import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { vi } from 'vitest'

import { routes } from '../app/routes'
import type { CurrentUser } from '../types/api'

type Handler = (request: { url: URL; body: unknown; headers: Headers }) => [number, unknown]

export interface ApiMock {
  calls: { method: string; path: string; query: Record<string, string>; body: unknown }[]
}

/**
 * Substitui o fetch: cada rota "MÉTODO /caminho" (sem /api/v1) devolve [status, corpo].
 * Rotas não mapeadas respondem 404 no envelope de erro da API.
 */
export function mockApi(routes: Record<string, Handler | [number, unknown]>): ApiMock {
  const mock: ApiMock = { calls: [] }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, init: RequestInit = {}) => {
      const url = new URL(input, 'http://localhost')
      const method = init.method ?? 'GET'
      const path = url.pathname.replace(/^\/api\/v1/, '')
      const raw = init.body
      const body =
        typeof raw === 'string'
          ? JSON.parse(raw)
          : raw instanceof URLSearchParams
            ? Object.fromEntries(raw)
            : undefined
      mock.calls.push({ method, path, query: Object.fromEntries(url.searchParams), body })
      const route = routes[`${method} ${path}`]
      const [status, payload] =
        typeof route === 'function'
          ? route({ url, body, headers: new Headers(init.headers) })
          : (route ?? [404, { error: { code: 'NOT_FOUND', message: `${method} ${path}`, details: null, request_id: null } }])
      return new Response(status === 204 ? null : JSON.stringify(payload), {
        status,
        headers: { 'Content-Type': 'application/json' },
      })
    }),
  )
  return mock
}

export const EMPTY_PAGE = { items: [], total: 0, page: 1, size: 20, pages: 0 }

/** Sessão salva como após um login real (o provedor valida com GET /auth/me). */
export function signIn(user: CurrentUser): void {
  const expiresAt = new Date(Date.now() + 60 * 60 * 1000).toISOString()
  sessionStorage.setItem(
    'labtrack.session',
    JSON.stringify({ token: 'token-de-teste', expiresAt, user }),
  )
}

/** Renderiza a aplicação real (rotas, autenticação, providers) numa rota. */
export function renderApp(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const view = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { ...view, router }
}
