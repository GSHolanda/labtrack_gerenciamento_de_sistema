import { describe, expect, it, vi } from 'vitest'

import { ApiError, buildUrl, configureApi, http } from './client'

function respond(status: number, body: unknown) {
  return vi.fn(async () => new Response(JSON.stringify(body), { status }))
}

describe('buildUrl', () => {
  it('repete listas e ignora filtros vazios', () => {
    expect(
      buildUrl('/samples', { status: ['RECEIVED', 'IN_ANALYSIS'], q: '', page: 2, x: undefined }),
    ).toBe('/api/v1/samples?status=RECEIVED&status=IN_ANALYSIS&page=2')
  })
})

describe('http', () => {
  it('envia o token e converte o envelope de erro', async () => {
    const fetchMock = respond(409, {
      error: {
        code: 'SAMPLE_HAS_OOS_RESULTS',
        message: 'Existem resultados fora da especificação.',
        details: { oos_tests: ['PH'] },
        request_id: 'req-1',
      },
    })
    vi.stubGlobal('fetch', fetchMock)
    configureApi({ getToken: () => 'abc', onUnauthorized: () => {} })

    const error = await http.post('/samples/1/approve', { password: 'x' }).catch((e) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 409,
      code: 'SAMPLE_HAS_OOS_RESULTS',
      details: { oos_tests: ['PH'] },
      requestId: 'req-1',
    })
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer abc')
  })

  it('401 numa requisição autenticada encerra a sessão; sem token, não', async () => {
    const onUnauthorized = vi.fn()
    vi.stubGlobal('fetch', respond(401, { error: { code: 'TOKEN_EXPIRED', message: 'x' } }))

    configureApi({ getToken: () => null, onUnauthorized })
    await http.get('/auth/me').catch(() => null)
    expect(onUnauthorized).not.toHaveBeenCalled()

    configureApi({ getToken: () => 'abc', onUnauthorized })
    await http.get('/auth/me').catch(() => null)
    expect(onUnauthorized).toHaveBeenCalledOnce()
  })

  it('mapeia erros de validação por campo', () => {
    const error = new ApiError(422, 'VALIDATION_ERROR', 'Dados inválidos.', [
      { field: 'body.lot_number', message: 'obrigatório' },
    ])
    expect(error.fieldErrors).toEqual({ lot_number: 'obrigatório' })
  })

  it('falha de rede vira NETWORK_ERROR', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('offline'))))
    await expect(http.get('/health')).rejects.toMatchObject({ code: 'NETWORK_ERROR', status: 0 })
  })
})
