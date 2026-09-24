import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { userWith } from '../../test/fixtures'
import { EMPTY_PAGE, mockApi, renderApp, signIn } from '../../test/utils'
import type { Instrument, InstrumentMessage, RoleCode } from '../../types/api'

const PH_METER: Instrument = {
  id: 1,
  code: 'PH-01',
  name: 'pHmetro de bancada',
  instrument_type: 'PH_METER',
  manufacturer: 'Metrohm',
  model: '913',
  serial_number: 'SN-0001',
  location: 'Sala 2',
  status: 'ACTIVE',
  calibration_due_date: '2027-03-31',
  calibration_valid: true,
  last_communication_at: '2026-09-24T10:00:00Z',
  online: true,
  created_at: '2026-01-10T10:00:00Z',
}

const EXPIRED: Instrument = {
  ...PH_METER,
  id: 2,
  code: 'KF-01',
  name: 'Karl Fischer',
  instrument_type: 'MOISTURE_ANALYZER',
  calibration_due_date: '2026-08-31',
  calibration_valid: false,
  last_communication_at: null,
  online: false,
}

const REJECTED: InstrumentMessage = {
  id: 5,
  received_at: '2026-09-24T10:05:00Z',
  status: 'REJECTED',
  sample_code: 'SMP-2026-0007',
  test_code: 'PH',
  value: '6.1000',
  unit: 'mV',
  error_code: 'UNIT_MISMATCH',
  error_message: 'Unidade diferente da especificada.',
  test_result_id: null,
  payload: { instrument_id: 'PH-01', sample_code: 'SMP-2026-0007', result: 6.1, unit: 'mV' },
}

function open(role: RoleCode, path: string, routes: Parameters<typeof mockApi>[0] = {}) {
  const user = userWith(role)
  signIn(user)
  const api = mockApi({
    'GET /auth/me': [200, user],
    'GET /instruments': [200, { ...EMPTY_PAGE, items: [PH_METER, EXPIRED], total: 2, pages: 1 }],
    'GET /instruments/1': [200, PH_METER],
    'GET /instruments/1/messages': [200, { ...EMPTY_PAGE, items: [REJECTED], total: 1, pages: 1 }],
    ...routes,
  })
  return { api, ...renderApp(path) }
}

describe('Equipamentos', () => {
  it('lista status, calibração e comunicação para qualquer perfil', async () => {
    open('ANALYST', '/instruments')

    const ph = (await screen.findByRole('link', { name: 'PH-01' })).closest('tr')!
    expect(within(ph).getByText('Online')).toBeInTheDocument()
    expect(within(ph).getByText('Válida até 31/03/2027')).toBeInTheDocument()
    const kf = screen.getByRole('link', { name: 'KF-01' }).closest('tr')!
    expect(within(kf).getByText('Vencida em 31/08/2026')).toBeInTheDocument()
    expect(within(kf).getByText('Offline')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Cadastrar equipamento' })).not.toBeInTheDocument()
  })

  it('o administrador cadastra e vê a chave uma única vez', async () => {
    const { api } = open('ADMIN', '/instruments', {
      'POST /instruments': ({ body }) => [
        201,
        { ...PH_METER, ...(body as object), id: 3, api_key: 'lt_inst_chave-exibida-uma-vez' },
      ],
    })
    await userEvent.click(await screen.findByRole('button', { name: 'Cadastrar equipamento' }))
    const form = screen.getByRole('dialog', { name: 'Cadastrar equipamento' })
    await userEvent.type(within(form).getByLabelText(/^Código/), 'VISC-01')
    await userEvent.type(within(form).getByLabelText(/^Nome/), 'Viscosímetro')
    await userEvent.selectOptions(within(form).getByLabelText(/^Tipo/), 'VISCOMETER')
    await userEvent.type(within(form).getByLabelText(/^Vencimento da calibração/), '2027-06-30')
    await userEvent.click(within(form).getByRole('button', { name: 'Cadastrar e gerar chave' }))

    const keyDialog = await screen.findByRole('dialog', { name: 'Chave de integração: VISC-01' })
    expect(within(keyDialog).getByTestId('api-key')).toHaveTextContent('lt_inst_chave-exibida-uma-vez')
    expect(within(keyDialog).getByText('Copie a chave agora')).toBeInTheDocument()
    expect(api.calls.find((call) => call.method === 'POST')?.body).toMatchObject({
      code: 'VISC-01',
      instrument_type: 'VISCOMETER',
      calibration_due_date: '2027-06-30',
      manufacturer: null,
    })

    await userEvent.click(within(keyDialog).getByRole('button', { name: 'Concluir' }))
    await waitFor(() => expect(screen.queryByTestId('api-key')).not.toBeInTheDocument())
  })

  it('detalhe mostra o log com o payload recusado e permite trocar a chave', async () => {
    const { api } = open('ADMIN', '/instruments/1', {
      'POST /instruments/1/rotate-key': () => [
        200,
        { ...PH_METER, api_key: 'lt_inst_nova-chave' },
      ],
    })

    const row = (await screen.findByText('UNIT_MISMATCH')).closest('tr')!
    expect(within(row).getByText('SMP-2026-0007 / PH')).toBeInTheDocument()
    expect(within(row).getByText('Unidade diferente da especificada.')).toBeInTheDocument()
    await userEvent.click(within(row).getByRole('button', { name: 'Mensagem' }))
    expect(screen.getByText(/"unit": "mV"/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Gerar nova chave' }))
    const dialog = screen.getByRole('dialog', { name: 'Gerar nova chave para PH-01' })
    const confirm = within(dialog).getByRole('button', { name: 'Revogar e gerar nova chave' })
    await userEvent.type(within(dialog).getByLabelText(/Motivo/), 'abc')
    expect(confirm).toBeDisabled() // motivo curto demais
    await userEvent.type(within(dialog).getByLabelText(/Motivo/), ' vazada')
    await userEvent.click(confirm)

    const keyDialog = await screen.findByRole('dialog', { name: 'Chave de integração: PH-01' })
    expect(within(keyDialog).getByText(/A chave anterior já deixou de funcionar/)).toBeInTheDocument()
    expect(api.calls.find((call) => call.path === '/instruments/1/rotate-key')?.body).toEqual({
      reason: 'abc vazada',
    })
  })

  it('o log pode ser filtrado por situação', async () => {
    const { api } = open('REVIEWER', '/instruments/1')
    await screen.findByText('UNIT_MISMATCH')
    expect(screen.queryByRole('button', { name: 'Gerar nova chave' })).not.toBeInTheDocument()

    await userEvent.selectOptions(screen.getByLabelText('Situação'), 'REJECTED')
    await waitFor(() =>
      expect(
        api.calls.filter((call) => call.path === '/instruments/1/messages').at(-1)?.query,
      ).toMatchObject({ status: 'REJECTED' }),
    )
  })
})
