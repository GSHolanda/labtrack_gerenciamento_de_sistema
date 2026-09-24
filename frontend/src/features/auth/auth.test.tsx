import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { userWith } from '../../test/fixtures'
import { EMPTY_PAGE, mockApi, renderApp, signIn } from '../../test/utils'

const analyst = userWith('ANALYST')

function login(username: string, role: 'ANALYST' | 'REVIEWER') {
  return [
    200,
    {
      access_token: `token-${username}`,
      token_type: 'bearer',
      expires_at: new Date(Date.now() + 3_600_000).toISOString(),
      user: userWith(role),
    },
  ] as [number, unknown]
}

describe('autenticação', () => {
  it('rota protegida leva ao login e volta para a página pedida', async () => {
    const api = mockApi({
      'POST /auth/login': login('carlos.silva', 'ANALYST'),
      'GET /samples': [200, EMPTY_PAGE],
      'GET /products': [200, EMPTY_PAGE],
      'GET /clients': [200, EMPTY_PAGE],
    })
    const { router } = renderApp('/samples')

    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/Usuário/), 'carlos.silva')
    await userEvent.type(screen.getByLabelText(/Senha/), 'Demo@2026')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByRole('heading', { name: 'Amostras' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/samples')
    expect(api.calls[0]).toMatchObject({
      method: 'POST',
      path: '/auth/login',
      body: { username: 'carlos.silva', password: 'Demo@2026' },
    })
    expect(JSON.parse(sessionStorage.getItem('labtrack.session')!).token).toBe(
      'token-carlos.silva',
    )
  })

  it('credenciais inválidas mostram a mensagem da API', async () => {
    mockApi({
      'POST /auth/login': [
        401,
        {
          error: {
            code: 'INVALID_CREDENTIALS',
            message: 'Usuário ou senha inválidos.',
            details: null,
            request_id: null,
          },
        },
      ],
    })
    renderApp('/login')

    await userEvent.type(await screen.findByLabelText(/Usuário/), 'x')
    await userEvent.type(screen.getByLabelText(/Senha/), 'y')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByText('Usuário ou senha inválidos.')).toBeInTheDocument()
  })

  it('sessão expirada no servidor volta ao login com aviso', async () => {
    signIn(analyst)
    mockApi({
      'GET /auth/me': [200, analyst],
      'GET /samples': [
        401,
        { error: { code: 'TOKEN_EXPIRED', message: 'Sessão expirada.', details: null } },
      ],
      'GET /results': [200, EMPTY_PAGE],
    })
    renderApp('/dashboard')

    expect(await screen.findByText(/Sua sessão expirou/)).toBeInTheDocument()
    expect(sessionStorage.getItem('labtrack.session')).toBeNull()
  })

  it('após sair, o próximo usuário começa no dashboard', async () => {
    signIn(analyst)
    mockApi({
      'GET /auth/me': [200, analyst],
      'GET /samples': [200, EMPTY_PAGE],
      'GET /products': [200, EMPTY_PAGE],
      'GET /clients': [200, EMPTY_PAGE],
      'GET /results': [200, EMPTY_PAGE],
      'POST /auth/login': login('ana.souza', 'REVIEWER'),
    })
    const { router } = renderApp('/samples')

    await userEvent.click(await screen.findByRole('button', { name: 'Sair' }))
    await userEvent.type(await screen.findByLabelText(/Usuário/), 'ana.souza')
    await userEvent.type(screen.getByLabelText(/Senha/), 'Demo@2026')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/dashboard'))
  })
})

describe('menu e rotas por permissão', () => {
  it.each([
    ['ANALYST', ['Dashboard', 'Amostras', 'Testes', 'Resultados', 'Equipamentos', 'Relatórios']],
    [
      'REVIEWER',
      ['Dashboard', 'Amostras', 'Testes', 'Resultados', 'Equipamentos', 'Audit Trail', 'Relatórios'],
    ],
    [
      'ADMIN',
      ['Dashboard', 'Amostras', 'Testes', 'Resultados', 'Equipamentos', 'Audit Trail', 'Administração'],
    ],
  ] as const)('%s vê apenas o que pode acessar', async (role, expected) => {
    const user = userWith(role)
    signIn(user)
    mockApi({
      'GET /auth/me': [200, user],
      'GET /samples': [200, EMPTY_PAGE],
      'GET /results': [200, EMPTY_PAGE],
    })
    renderApp('/dashboard')

    const menu = await screen.findByLabelText('Menu principal')
    const links = within(menu).getAllByRole('link').map((link) => link.textContent)
    expect(links).toEqual(expected)
  })

  it('acesso direto a uma área sem permissão mostra acesso negado', async () => {
    signIn(analyst)
    mockApi({ 'GET /auth/me': [200, analyst] })
    renderApp('/audit')

    expect(await screen.findByRole('heading', { name: 'Acesso negado' })).toBeInTheDocument()
  })
})
