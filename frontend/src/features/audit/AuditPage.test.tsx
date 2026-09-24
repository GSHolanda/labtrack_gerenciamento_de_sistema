import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { timelineEvent, userWith } from '../../test/fixtures'
import { EMPTY_PAGE, mockApi, renderApp, signIn } from '../../test/utils'
import type { AuditRecord, RoleCode } from '../../types/api'

function record(overrides: Partial<AuditRecord> = {}): AuditRecord {
  const { is_correction: _correction, has_oos: _oos, ...event } = timelineEvent({
    id: 41,
    action: 'SAMPLE_STATUS_CHANGED',
    entity_type: 'sample',
    entity_id: '7',
    entity_label: 'SMP-2026-0007',
    old_value: { status: 'IN_ANALYSIS' },
    new_value: { status: 'AWAITING_REVIEW' },
  })
  return {
    ...event,
    request_id: 'req-123',
    ip_address: '10.0.0.5',
    previous_hash: 'a'.repeat(64),
    record_hash: 'b'.repeat(64),
    ...overrides,
  }
}

const PAGE = { ...EMPTY_PAGE, items: [record()], total: 1, pages: 1 }

function open(role: RoleCode, path = '/audit', routes: Parameters<typeof mockApi>[0] = {}) {
  const user = userWith(role)
  signIn(user)
  const api = mockApi({ 'GET /auth/me': [200, user], 'GET /audit-logs': [200, PAGE], ...routes })
  return { api, ...renderApp(path) }
}

describe('Audit trail', () => {
  it('mostra quem fez o quê, os valores e os hashes do registro', async () => {
    open('MANAGER')

    const row = (await screen.findByText('SMP-2026-0007')).closest('tr')!
    expect(within(row).getByText('Carlos Silva')).toBeInTheDocument()
    expect(within(row).getByText('status: IN_ANALYSIS')).toBeInTheDocument()
    expect(within(row).getByText('status: AWAITING_REVIEW')).toBeInTheDocument()
    expect(within(row).getByRole('link', { name: 'Abrir amostra' })).toHaveAttribute(
      'href',
      '/samples/7',
    )

    await userEvent.click(within(row).getByRole('button', { name: 'Detalhes' }))
    expect(screen.getByText('#41')).toBeInTheDocument()
    expect(screen.getByText('req-123')).toBeInTheDocument()
    expect(screen.getByText('b'.repeat(64))).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: 'Ocultar' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
  })

  it('verifica a integridade da cadeia e mostra o primeiro registro inválido', async () => {
    let valid = true
    open('REVIEWER', '/audit', {
      'GET /audit-logs/verify': () => [
        200,
        valid
          ? { valid: true, checked_records: 120, first_invalid_id: null, error_code: null }
          : {
              valid: false,
              checked_records: 3,
              first_invalid_id: 3,
              error_code: 'RECORD_HASH_MISMATCH',
            },
      ],
    })

    const verify = await screen.findByRole('button', { name: 'Verificar integridade' })
    await userEvent.click(verify)
    expect(await screen.findByText('Cadeia de hashes íntegra')).toBeInTheDocument()
    expect(screen.getByText(/120 registros verificados/)).toBeInTheDocument()

    valid = false
    await userEvent.click(verify)
    expect(await screen.findByText('Inconsistência na cadeia de hashes')).toBeInTheDocument()
    expect(screen.getByText(/#3 \(\s*RECORD_HASH_MISMATCH\)/)).toBeInTheDocument()
  })

  it('filtra pela URL e envia os filtros à API', async () => {
    const { api } = open('MANAGER', '/audit?sample_id=7')

    expect(await screen.findByText('Amostra #7')).toBeInTheDocument()
    await waitFor(() => expect(api.calls.at(-1)?.query).toMatchObject({ sample_id: '7' }))

    await userEvent.selectOptions(screen.getByLabelText('Ação'), 'RESULT_AMENDED')
    await waitFor(() =>
      expect(api.calls.at(-1)?.query).toMatchObject({ sample_id: '7', action: 'RESULT_AMENDED' }),
    )

    await userEvent.click(screen.getByRole('button', { name: 'Remover filtro de amostra' }))
    await waitFor(() => expect(api.calls.at(-1)?.query.sample_id).toBeUndefined())
    expect(api.calls.at(-1)?.query.action).toBe('RESULT_AMENDED')
  })

  it('não existe para o analista', async () => {
    open('ANALYST')
    expect(await screen.findByText('Acesso negado')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Audit Trail' })).not.toBeInTheDocument()
  })
})
