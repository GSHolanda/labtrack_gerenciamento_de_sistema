import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { userWith } from '../../test/fixtures'
import { EMPTY_PAGE, mockApi, renderApp, signIn } from '../../test/utils'
import type { DashboardCharts, DashboardSummary, PeriodTotals } from '../../types/api'

const totals = (overrides: Partial<PeriodTotals> = {}): PeriodTotals => ({
  received: 0,
  approved: 0,
  rejected: 0,
  cancelled: 0,
  approval_rate: null,
  average_processing_hours: null,
  median_processing_hours: null,
  oos_results: 0,
  samples_with_oos: 0,
  ...overrides,
})

const PERIOD = {
  days: 90,
  start: '2026-06-26T12:00:00Z',
  end: '2026-09-24T12:00:00Z',
  timezone: 'America/Sao_Paulo',
}

const SUMMARY: DashboardSummary = {
  generated_at: '2026-09-24T12:00:00Z',
  period: PERIOD,
  workload: {
    open: 7,
    received: 1,
    in_analysis: 3,
    awaiting_review: 3,
    open_with_oos: 1,
    urgent_open: 1,
  },
  current: totals({
    received: 20,
    approved: 10,
    rejected: 2,
    cancelled: 1,
    approval_rate: 0.8333,
    average_processing_hours: 50,
    median_processing_hours: 49,
    oos_results: 5,
    samples_with_oos: 5,
  }),
  previous: totals({ received: 12, approved: 8, rejected: 1, approval_rate: 0.8889, oos_results: 2 }),
}

const CHARTS: DashboardCharts = {
  generated_at: '2026-09-24T12:00:00Z',
  period: PERIOD,
  granularity: 'week',
  throughput: [
    { bucket: '2026-08-31', approved: 3, rejected: 1, approval_rate: 0.75 },
    { bucket: '2026-09-07', approved: 0, rejected: 0, approval_rate: null },
  ],
  by_status: [
    { status: 'RECEIVED', count: 1 },
    { status: 'IN_ANALYSIS', count: 3 },
    { status: 'AWAITING_REVIEW', count: 3 },
    { status: 'APPROVED', count: 10 },
    { status: 'REJECTED', count: 2 },
    { status: 'CANCELLED', count: 1 },
  ],
  oos_by_test: [
    { test_code: 'ASSAY', test_name: 'Teor do ativo', results: 10, oos: 2, oos_rate: 0.2 },
  ],
}

function open(role: 'MANAGER' | 'ANALYST' = 'MANAGER') {
  const user = userWith(role)
  signIn(user)
  const api = mockApi({
    'GET /auth/me': [200, user],
    'GET /dashboard/summary': [200, SUMMARY],
    'GET /dashboard/charts': [200, CHARTS],
    'GET /samples': [200, EMPTY_PAGE],
  })
  return { api, ...renderApp('/dashboard') }
}

function tile(label: string): HTMLElement {
  return screen.getByText(label, { selector: '.stat-tile__label' }).closest('.stat-tile')!
}

describe('dashboard', () => {
  it('mostra a carga atual e os indicadores do período com variação', async () => {
    open()

    expect(await screen.findByRole('heading', { name: 'Agora' })).toBeInTheDocument()
    expect(within(tile('Em aberto')).getByText('7')).toBeInTheDocument()
    expect(tile('Em aberto com OOS vigente')).toHaveClass('stat-tile--alert')

    const approved = tile('Aprovadas')
    expect(within(approved).getByText('10')).toBeInTheDocument()
    expect(within(approved).getByText('+2', { exact: false })).toBeInTheDocument()
    expect(approved.querySelector('.stat-tile__delta--good')).not.toBeNull()

    // Mais reprovações é piora; o sinal vem com texto, não só com cor.
    const rejected = tile('Reprovadas')
    expect(rejected.querySelector('.stat-tile__delta--bad')).not.toBeNull()
    expect(within(rejected).getByText('(piora)', { exact: false })).toBeInTheDocument()

    expect(within(tile('Taxa de aprovação')).getByText('83,3%')).toBeInTheDocument()
    expect(within(tile('Tempo até a decisão')).getByText('2 d 2 h')).toBeInTheDocument()
    expect(within(tile('Resultados OOS')).getByText(/Em 5 amostra/)).toBeInTheDocument()
  })

  it('o período vale para indicadores e gráficos e fica na URL', async () => {
    const { api, router } = open()
    await screen.findByRole('heading', { name: 'Agora' })
    expect(screen.getByRole('button', { name: '90 dias' })).toHaveAttribute('aria-pressed', 'true')

    await userEvent.click(screen.getByRole('button', { name: '30 dias' }))

    await waitFor(() => expect(router.state.location.search).toBe('?period=30'))
    const requested = (path: string) =>
      api.calls.filter((call) => call.path === path).map((call) => call.query.period_days)
    await waitFor(() => expect(requested('/dashboard/summary')).toEqual(['90', '30']))
    expect(requested('/dashboard/charts')).toEqual(['90', '30'])
    expect(screen.getByRole('button', { name: '30 dias' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('cada gráfico tem uma tabela com os mesmos valores', async () => {
    open()

    const card = (await screen.findByRole('heading', { name: 'Amostras decididas' })).closest(
      'figure',
    )!
    expect(within(card).getByText('Aprovadas')).toBeInTheDocument() // legenda com 2 séries
    await userEvent.click(within(card).getByRole('button', { name: 'Tabela' }))
    const rows = within(card).getAllByRole('row')
    expect(rows[1]).toHaveTextContent('Semana de 31/08/2026' + '3' + '1' + '75%')

    const oos = screen.getByRole('heading', { name: /Resultados OOS por teste/ }).closest('figure')!
    await userEvent.click(within(oos).getByRole('button', { name: 'Tabela' }))
    expect(within(oos).getByRole('row', { name: /Teor do ativo/ })).toHaveTextContent('20%')
  })

  it('mostra aviso quando o período não tem decisões', async () => {
    const user = userWith('ANALYST')
    signIn(user)
    mockApi({
      'GET /auth/me': [200, user],
      'GET /dashboard/summary': [200, SUMMARY],
      'GET /dashboard/charts': [
        200,
        { ...CHARTS, throughput: CHARTS.throughput.map((p) => ({ ...p, approved: 0, rejected: 0 })) },
      ],
      'GET /samples': [200, EMPTY_PAGE],
    })
    renderApp('/dashboard')

    expect(
      await screen.findByText('Nenhuma amostra aprovada ou reprovada no período.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Suas amostras em andamento')).toBeInTheDocument()
  })
})
