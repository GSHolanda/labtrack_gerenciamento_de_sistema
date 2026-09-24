import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { userWith } from '../../test/fixtures'
import { EMPTY_PAGE, mockApi, renderApp, signIn } from '../../test/utils'
import type { Client, Product, RoleCode, Specification, TestDefinition, User } from '../../types/api'

const page = <T,>(items: T[]) => ({ ...EMPTY_PAGE, items, total: items.length, pages: 1 })

const ANA: User = {
  id: 3,
  username: 'ana.souza',
  email: 'ana@labtrack.dev',
  full_name: 'Ana Souza',
  role: 'REVIEWER',
  is_active: true,
  last_login_at: null,
  created_at: '2026-01-10T10:00:00Z',
}

const CLIENT: Client = {
  id: 1,
  code: 'CLI-001',
  name: 'Farmacêutica Aurora',
  tax_id: null,
  contact_email: 'qualidade@aurora.com',
  is_active: true,
  created_at: '2026-01-10T10:00:00Z',
}

const PRODUCT: Product = {
  id: 1,
  code: 'PRD-001',
  name: 'Xampu Neutro',
  category: 'Cosmético',
  description: null,
  is_active: true,
  created_at: '2026-01-10T10:00:00Z',
}

const definition = (id: number, code: string, name: string): TestDefinition => ({
  id,
  code,
  name,
  unit: 'pH',
  spec_min: '6.5000',
  spec_max: '7.5000',
  method: 'Potenciometria',
  instrument_type: null,
  decimal_places: 2,
  description: null,
  is_active: true,
})

const PH_PLAN: Specification = {
  test_definition_id: 1,
  test_code: 'PH',
  test_name: 'pH',
  unit: 'pH',
  spec_min: '5.5000',
  spec_max: '7.0000',
  overrides_default: true,
  product_spec_min: '5.5000',
  product_spec_max: '7.0000',
}

function open(role: RoleCode, path = '/admin', routes: Parameters<typeof mockApi>[0] = {}) {
  const user = userWith(role)
  signIn(user)
  const api = mockApi({
    'GET /auth/me': [200, user],
    'GET /users': [200, page([ANA])],
    'GET /clients': [200, page([CLIENT])],
    'GET /products': [200, page([PRODUCT])],
    'GET /test-definitions': [
      200,
      page([definition(1, 'PH', 'pH'), definition(2, 'DENSITY', 'Densidade')]),
    ],
    'GET /products/1/specifications': [200, [PH_PLAN]],
    ...routes,
  })
  return { api, ...renderApp(path) }
}

describe('Administração', () => {
  it('abre nas abas permitidas e cria usuário sem excluir ninguém', async () => {
    const { api } = open('ADMIN', '/admin', {
      'POST /users': ({ body }) => [201, { ...ANA, ...(body as object), id: 9 }],
    })

    expect(await screen.findByRole('tab', { name: 'Usuários' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    const row = (await screen.findByText('ana.souza')).closest('tr')!
    expect(within(row).getByText('Ana Souza')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Novo usuário' }))
    const dialog = screen.getByRole('dialog', { name: 'Novo usuário' })
    await userEvent.type(within(dialog).getByLabelText(/^Login/), 'Joao.Lima')
    await userEvent.type(within(dialog).getByLabelText(/^Nome completo/), 'João Lima')
    await userEvent.type(within(dialog).getByLabelText(/^E-mail/), 'joao@labtrack.dev')
    await userEvent.selectOptions(within(dialog).getByLabelText('Perfil'), 'MANAGER')
    await userEvent.type(within(dialog).getByLabelText(/^Senha/), 'Senha@2026')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Criar usuário' }))

    expect(await screen.findByText('Usuário joao.lima criado')).toBeInTheDocument()
    expect(api.calls.find((call) => call.method === 'POST')?.body).toEqual({
      username: 'joao.lima',
      full_name: 'João Lima',
      email: 'joao@labtrack.dev',
      role: 'MANAGER',
      password: 'Senha@2026',
    })
  })

  it('desativa um usuário em vez de excluir', async () => {
    const { api } = open('ADMIN', '/admin', {
      'PATCH /users/3': ({ body }) => [200, { ...ANA, ...(body as object) }],
    })
    const row = (await screen.findByText('ana.souza')).closest('tr')!
    await userEvent.click(within(row).getByRole('button', { name: 'Editar' }))
    const dialog = screen.getByRole('dialog', { name: 'Editar ana.souza' })
    await userEvent.click(within(dialog).getByLabelText(/^Ativo/))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Salvar alterações' }))

    expect(await screen.findByText('Usuário ana.souza atualizado')).toBeInTheDocument()
    expect(api.calls.find((call) => call.method === 'PATCH')?.body).toMatchObject({
      is_active: false,
    })
    expect(api.calls.some((call) => call.method === 'DELETE')).toBe(false)
  })

  it('cadastra cliente e mostra erro de duplicidade vindo da API', async () => {
    open('ADMIN', '/admin?tab=clients', {
      'POST /clients': [
        409,
        {
          error: {
            code: 'DUPLICATE_CLIENT',
            message: 'Já existe cliente com o código CLI-001.',
            details: null,
            request_id: null,
          },
        },
      ],
    })
    expect(await screen.findByText('Farmacêutica Aurora')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Novo cliente' }))
    const dialog = screen.getByRole('dialog', { name: 'Novo cliente' })
    await userEvent.type(within(dialog).getByLabelText(/^Código/), 'CLI-001')
    await userEvent.type(within(dialog).getByLabelText(/^Nome/), 'Outra Aurora')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Criar cliente' }))

    expect(
      await within(dialog).findByText('Já existe cliente com o código CLI-001.'),
    ).toBeInTheDocument()
  })

  it('edita o plano analítico com limites próprios do produto', async () => {
    const { api } = open('ADMIN', '/admin?tab=products', {
      'PUT /products/1/specifications': ({ body }) => [200, body],
    })
    const row = (await screen.findByText('Xampu Neutro')).closest('tr')!
    await userEvent.click(within(row).getByRole('button', { name: 'Plano analítico' }))
    const dialog = await screen.findByRole('dialog', { name: 'Plano analítico: Xampu Neutro' })

    expect(await within(dialog).findByLabelText('Mínimo para pH')).toHaveValue('5,5')
    await userEvent.selectOptions(within(dialog).getByLabelText('Teste a adicionar'), '2')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Adicionar' }))
    await userEvent.type(within(dialog).getByLabelText('Máximo para Densidade'), '1,05')

    await userEvent.clear(within(dialog).getByLabelText('Mínimo para pH'))
    await userEvent.type(within(dialog).getByLabelText('Mínimo para pH'), 'x')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Salvar plano' }))
    expect(within(dialog).getByText('Os limites devem ser números.')).toBeInTheDocument()

    await userEvent.clear(within(dialog).getByLabelText('Mínimo para pH'))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Salvar plano' }))
    expect(await screen.findByText('Plano analítico salvo')).toBeInTheDocument()
    await waitFor(() =>
      expect(api.calls.find((call) => call.method === 'PUT')?.body).toEqual([
        { test_definition_id: 1, spec_min: null, spec_max: '7' },
        { test_definition_id: 2, spec_min: null, spec_max: '1.05' },
      ]),
    )
  })

  it('não existe para quem não administra', async () => {
    open('REVIEWER')
    expect(await screen.findByText('Acesso negado')).toBeInTheDocument()
  })
})
