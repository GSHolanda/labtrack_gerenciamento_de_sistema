import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { userWith } from '../../test/fixtures'
import { EMPTY_PAGE, mockApi, renderApp, signIn } from '../../test/utils'
import type { ResultListItem } from '../../types/api'

function result(overrides: Partial<ResultListItem> = {}): ResultListItem {
  return {
    id: 31,
    sample_test_id: 11,
    value: '7.4000',
    unit: 'pH',
    spec_status: 'OOS',
    source: 'INSTRUMENT',
    version: 1,
    is_current: false,
    entered_by: null,
    instrument_code: 'PH-01',
    entered_at: '2026-09-20T12:30:00Z',
    change_reason: null,
    comment: null,
    sample_id: 7,
    sample_code: 'SMP-2026-0007',
    test_code: 'PH',
    test_name: 'pH',
    decimal_places: 2,
    spec_min: '5.5000',
    spec_max: '7.0000',
    ...overrides,
  }
}

const RESULTS = [
  result(),
  result({
    id: 32,
    value: '6.9000',
    spec_status: 'IN_SPEC',
    source: 'MANUAL',
    version: 2,
    is_current: true,
    entered_by: { id: 2, full_name: 'Carlos Silva' },
    instrument_code: null,
  }),
]

function open(path = '/results') {
  const user = userWith('REVIEWER')
  signIn(user)
  const api = mockApi({
    'GET /auth/me': [200, user],
    'GET /test-definitions': [200, EMPTY_PAGE],
    'GET /results': [200, { ...EMPTY_PAGE, items: RESULTS, total: 2, pages: 1 }],
  })
  return { api, ...renderApp(path) }
}

describe('Resultados', () => {
  it('mostra versões corrigidas, origem e OOS sem esconder dígitos', async () => {
    open('/results?spec_status=OOS&history=1')

    const [oos, current] = (await screen.findAllByRole('link', { name: 'SMP-2026-0007' })).map(
      (link) => link.closest('tr')!,
    )
    expect(oos).toHaveClass('row--oos')
    expect(within(oos).getByText('7,40 pH')).toBeInTheDocument()
    expect(within(oos).getByText('5,50 a 7,00 pH')).toBeInTheDocument()
    expect(within(oos).getByText(/v1\s*· substituída/)).toBeInTheDocument()
    expect(within(oos).getByText('PH-01')).toBeInTheDocument()
    expect(within(oos).getByText('OOS')).toBeInTheDocument()
    expect(within(current).getByText('Carlos Silva')).toBeInTheDocument()
    expect(within(current).getByText('Conforme')).toBeInTheDocument()
    expect(screen.getByLabelText(/Incluir versões corrigidas/)).toBeChecked()
  })

  it('filtros vão para a API: só vigentes por padrão, histórico sob pedido', async () => {
    const { api } = open()
    await screen.findAllByRole('link', { name: 'SMP-2026-0007' })
    const lastQuery = () => api.calls.filter((call) => call.path === '/results').at(-1)?.query
    expect(lastQuery()).toMatchObject({ current_only: 'true' })

    await userEvent.selectOptions(screen.getByLabelText('Situação'), 'OOS')
    await waitFor(() => expect(lastQuery()).toMatchObject({ spec_status: 'OOS' }))

    await userEvent.click(screen.getByLabelText(/Incluir versões corrigidas/))
    await waitFor(() =>
      expect(lastQuery()).toMatchObject({ spec_status: 'OOS', current_only: 'false' }),
    )

    await userEvent.click(screen.getByRole('button', { name: 'Limpar filtros' }))
    await waitFor(() => expect(lastQuery()).toMatchObject({ current_only: 'true' }))
    expect(lastQuery()?.spec_status).toBeUndefined()
  })
})
