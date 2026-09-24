import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { sampleDetail, sampleTest, timelineEvent, userWith } from '../../test/fixtures'
import { mockApi, renderApp, signIn } from '../../test/utils'
import type { RoleCode, SampleDetail } from '../../types/api'

const TIMELINE = {
  items: [
    timelineEvent({
      action: 'RESULT_ENTERED',
      has_oos: true,
      new_value: { value: '8.1', unit: 'pH', spec_status: 'OOS', source: 'MANUAL' },
    }),
  ],
  total: 1,
  page: 1,
  size: 100,
  pages: 1,
}

const oosResult = {
  id: 31,
  sample_test_id: 11,
  value: '8.1000',
  unit: 'pH',
  spec_status: 'OOS' as const,
  source: 'MANUAL' as const,
  version: 1,
  is_current: true,
  entered_by: { id: 2, full_name: 'Carlos Silva' },
  instrument_code: null,
  entered_at: '2026-09-20T12:30:00Z',
  change_reason: null,
  comment: null,
}

const awaitingWithOos = sampleDetail({
  status: 'AWAITING_REVIEW',
  allowed_actions: ['approve', 'reject', 'return_to_analysis', 'cancel'],
  tests_completed: 1,
  has_oos: true,
  oos_tests: ['PH'],
  tests: [
    sampleTest({
      status: 'COMPLETED',
      current_result: oosResult,
      result_versions: 1,
      had_oos: true,
    }),
  ],
})

function open(role: RoleCode, sample: SampleDetail, extra: Parameters<typeof mockApi>[0] = {}) {
  const user = userWith(role)
  signIn(user)
  const api = mockApi({
    'GET /auth/me': [200, user],
    [`GET /samples/${sample.id}`]: [200, sample],
    [`GET /samples/${sample.id}/timeline`]: [200, TIMELINE],
    ...extra,
  })
  renderApp(`/samples/${sample.id}`)
  return api
}

describe('detalhe da amostra', () => {
  it('revisor não aprova com OOS vigente, mas pode reprovar ou devolver', async () => {
    open('REVIEWER', awaitingWithOos)

    expect(await screen.findByText('Resultado fora da especificação (OOS)')).toBeInTheDocument()
    const approve = screen.getByRole('button', { name: 'Aprovar' })
    expect(approve).toBeDisabled()
    expect(approve).toHaveAttribute('title', 'Resultado fora da especificação: PH.')
    expect(screen.getByRole('button', { name: 'Reprovar' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Devolver para análise' })).toBeEnabled()
    expect(screen.queryByRole('button', { name: 'Cancelar amostra' })).not.toBeInTheDocument()
    // Timeline destaca o OOS
    expect(await screen.findByText('Resultado de PH: 8,1 pH')).toBeInTheDocument()
  })

  it('analista não vê ações de revisão', async () => {
    open('ANALYST', awaitingWithOos)

    await screen.findByText('Resultado fora da especificação (OOS)')
    for (const name of ['Aprovar', 'Reprovar', 'Devolver para análise', 'Cancelar amostra']) {
      expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
    }
    expect(screen.queryByRole('button', { name: 'Corrigir' })).not.toBeInTheDocument()
  })

  it('aprovação exige a senha e atualiza a tela', async () => {
    const inSpec = sampleDetail({
      ...awaitingWithOos,
      has_oos: false,
      oos_tests: [],
      tests: [
        sampleTest({
          status: 'COMPLETED',
          current_result: { ...oosResult, value: '6.8', spec_status: 'IN_SPEC' },
          result_versions: 1,
        }),
      ],
    })
    const approved = {
      ...inSpec,
      status: 'APPROVED' as const,
      allowed_actions: [],
      reviewed_by: { id: 3, full_name: 'Ana Souza' },
      reviewed_at: '2026-09-21T12:00:00Z',
      review_comment: 'Conferido',
    }
    const api = open('REVIEWER', inSpec, { 'POST /samples/7/approve': [200, approved] })

    await userEvent.click(await screen.findByRole('button', { name: 'Aprovar' }))
    const dialog = screen.getByRole('dialog')
    const sign = within(dialog).getByRole('button', { name: 'Assinar e aprovar' })
    expect(sign).toBeDisabled()
    await userEvent.type(within(dialog).getByLabelText(/Sua senha/), 'Demo@2026')
    await userEvent.type(within(dialog).getByLabelText(/Comentário/), 'Conferido')
    await userEvent.click(sign)

    expect(await screen.findByText(/Aprovada por Ana Souza/)).toBeInTheDocument()
    expect(api.calls.find((call) => call.path === '/samples/7/approve')?.body).toEqual({
      password: 'Demo@2026',
      comment: 'Conferido',
    })
  })

  it('envio para revisão fica bloqueado com teste pendente', async () => {
    open('ANALYST', sampleDetail())

    const submit = await screen.findByRole('button', { name: 'Enviar para revisão' })
    expect(submit).toBeDisabled()
    expect(submit).toHaveAttribute('title', 'Existem 1 teste(s) sem resultado.')
  })

  it('lançamento mostra a prévia OOS e envia o decimal com ponto', async () => {
    const api = open('ANALYST', sampleDetail(), {
      'POST /sample-tests/11/results': [201, { ...oosResult, value: '7.5' }],
    })

    await userEvent.click(await screen.findByRole('button', { name: 'Lançar' }))
    const dialog = screen.getByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText(/Resultado/), '7,5')
    expect(within(dialog).getByText('Fora da especificação')).toBeInTheDocument()
    await userEvent.clear(within(dialog).getByLabelText(/Resultado/))
    await userEvent.type(within(dialog).getByLabelText(/Resultado/), '7,0')
    expect(within(dialog).getByText('Dentro da especificação')).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Registrar resultado' }))

    await waitFor(() =>
      expect(api.calls.find((call) => call.method === 'POST')?.body).toEqual({
        value: '7.0',
        comment: null,
        change_reason: null,
      }),
    )
  })

  it('correção exige justificativa', async () => {
    const completed = sampleDetail({
      tests_completed: 1,
      tests: [sampleTest({ status: 'COMPLETED', current_result: oosResult, result_versions: 1 })],
    })
    const api = open('ANALYST', completed)

    await userEvent.click(await screen.findByRole('button', { name: 'Corrigir' }))
    const dialog = screen.getByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText(/Resultado/), '6,9')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Registrar correção' }))

    expect(within(dialog).getByText('Mínimo de 5 caracteres.')).toBeInTheDocument()
    expect(api.calls.some((call) => call.method === 'POST')).toBe(false)
  })

  it('reprovação exige justificativa e mostra o erro da API sem fechar', async () => {
    let attempts = 0
    const api = open('REVIEWER', awaitingWithOos, {
      [`POST /samples/${awaitingWithOos.id}/reject`]: ({ body }) => {
        attempts += 1
        return attempts === 1
          ? [
              409,
              {
                error: {
                  code: 'CONCURRENT_MODIFICATION',
                  message: 'A amostra foi alterada por outro usuário.',
                  details: null,
                  request_id: null,
                },
              },
            ]
          : [200, { ...awaitingWithOos, status: 'REJECTED', allowed_actions: [], ...(body as object) }]
      },
    })

    await userEvent.click(await screen.findByRole('button', { name: 'Reprovar' }))
    const dialog = screen.getByRole('dialog', { name: `Reprovar ${awaitingWithOos.sample_code}` })
    const confirm = within(dialog).getByRole('button', { name: 'Reprovar amostra' })
    await userEvent.type(within(dialog).getByLabelText(/^Justificativa/), 'pH')
    expect(confirm).toBeDisabled()

    await userEvent.type(within(dialog).getByLabelText(/^Justificativa/), ' acima do limite')
    await userEvent.click(confirm)
    expect(await within(dialog).findByText('A amostra foi alterada por outro usuário.')).toBeInTheDocument()

    await userEvent.click(within(dialog).getByRole('button', { name: 'Reprovar amostra' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    const calls = api.calls.filter((call) => call.path.endsWith('/reject'))
    expect(calls.map((call) => call.body)).toEqual([
      { reason: 'pH acima do limite' },
      { reason: 'pH acima do limite' },
    ])
  })

  it('gestor cancela a amostra com justificativa', async () => {
    const received = sampleDetail({ status: 'RECEIVED', allowed_actions: ['start_analysis', 'cancel'] })
    const api = open('MANAGER', received, {
      [`POST /samples/${received.id}/cancel`]: [
        200,
        { ...received, status: 'CANCELLED', allowed_actions: [] },
      ],
    })

    expect(await screen.findByRole('button', { name: 'Cancelar amostra' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Iniciar análise' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Cancelar amostra' }))
    const dialog = screen.getByRole('dialog', { name: `Cancelar ${received.sample_code}` })
    await userEvent.type(within(dialog).getByLabelText(/^Justificativa/), 'Registro em duplicidade')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancelar amostra' }))

    expect(await screen.findByText(`Cancelar amostra: ${received.sample_code}`)).toBeInTheDocument()
    expect(api.calls.find((call) => call.path.endsWith('/cancel'))?.body).toEqual({
      reason: 'Registro em duplicidade',
    })
  })
})
