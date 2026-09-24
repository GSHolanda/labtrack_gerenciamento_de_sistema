import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { userWith } from '../../test/fixtures'
import { EMPTY_PAGE, mockApi, renderApp, signIn } from '../../test/utils'
import type { RoleCode, TestDefinition } from '../../types/api'

const MOISTURE: TestDefinition = {
  id: 3,
  code: 'MOISTURE',
  name: 'Umidade',
  unit: '%',
  spec_min: null,
  spec_max: '0.5000',
  method: 'Karl Fischer',
  instrument_type: 'MOISTURE_ANALYZER',
  decimal_places: 2,
  description: null,
  is_active: true,
}

function open(role: RoleCode, routes: Parameters<typeof mockApi>[0] = {}) {
  const user = userWith(role)
  signIn(user)
  const api = mockApi({
    'GET /auth/me': [200, user],
    'GET /test-definitions': [200, { ...EMPTY_PAGE, items: [MOISTURE], total: 1, pages: 1 }],
    ...routes,
  })
  return { api, ...renderApp('/tests') }
}

describe('Catálogo de testes', () => {
  it('todos consultam; só o administrador cria e edita', async () => {
    open('ANALYST')
    const row = (await screen.findByText('MOISTURE')).closest('tr')!
    expect(within(row).getByText('≤ 0,50 %')).toBeInTheDocument()
    expect(within(row).getByText('Analisador de umidade')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Novo tipo de teste' })).not.toBeInTheDocument()
    expect(within(row).queryByRole('button', { name: 'Editar' })).not.toBeInTheDocument()
  })

  it('valida os limites antes de enviar e cria com decimais em texto', async () => {
    const { api } = open('ADMIN', {
      'POST /test-definitions': ({ body }) => [201, { ...MOISTURE, ...(body as object), id: 9 }],
    })
    await userEvent.click(await screen.findByRole('button', { name: 'Novo tipo de teste' }))
    const dialog = screen.getByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText(/^Código/), 'VISC')
    await userEvent.type(within(dialog).getByLabelText(/^Nome/), 'Viscosidade')
    await userEvent.type(within(dialog).getByLabelText(/^Unidade/), 'cP')
    await userEvent.type(within(dialog).getByLabelText(/^Método/), 'Brookfield')

    await userEvent.click(within(dialog).getByRole('button', { name: 'Criar' }))
    expect(within(dialog).getByText('Informe ao menos um limite de especificação.')).toBeInTheDocument()

    await userEvent.type(within(dialog).getByLabelText('Limite mínimo'), 'abc')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Criar' }))
    expect(within(dialog).getByText('Os limites devem ser números.')).toBeInTheDocument()
    expect(api.calls.some((call) => call.method === 'POST')).toBe(false)

    await userEvent.clear(within(dialog).getByLabelText('Limite mínimo'))
    await userEvent.type(within(dialog).getByLabelText('Limite mínimo'), '2800,5')
    await userEvent.type(within(dialog).getByLabelText('Limite máximo'), '3200')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Criar' }))

    expect(await screen.findByText('Tipo de teste VISC criado')).toBeInTheDocument()
    const post = api.calls.find((call) => call.method === 'POST')!
    expect(post.body).toMatchObject({
      code: 'VISC',
      name: 'Viscosidade',
      unit: 'cP',
      spec_min: '2800.5',
      spec_max: '3200',
      method: 'Brookfield',
    })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('mostra no campo o erro de validação devolvido pela API', async () => {
    open('ADMIN', {
      'PATCH /test-definitions/3': [
        422,
        {
          error: {
            code: 'VALIDATION_ERROR',
            message: 'Dados inválidos.',
            details: [{ field: 'body.spec_max', message: 'Limite máximo menor que o mínimo.' }],
            request_id: null,
          },
        },
      ],
    })
    const row = (await screen.findByText('MOISTURE')).closest('tr')!
    await userEvent.click(within(row).getByRole('button', { name: 'Editar' }))
    const dialog = screen.getByRole('dialog', { name: 'Editar MOISTURE' })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Salvar alterações' }))

    expect(await within(dialog).findByText('Limite máximo menor que o mínimo.')).toBeInTheDocument()
  })
})
