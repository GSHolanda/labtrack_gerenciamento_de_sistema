import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { sampleDetail, sampleReport, userWith } from '../../test/fixtures'
import { EMPTY_PAGE, mockApi, renderApp, signIn } from '../../test/utils'
import type { RoleCode, SampleDetail, SampleSummary } from '../../types/api'

const REPORT = sampleReport()
const HASH = REPORT.content_hash

function pdfResponse(headers: Record<string, string> = {}) {
  // Corpo em texto: o Blob do jsdom não é aceito pela Response do Node.
  return new Response('%PDF-1.4', {
    status: 200,
    headers: {
      'Content-Type': 'application/pdf',
      'Content-Disposition': 'attachment; filename="relatorio-SMP-2026-0001.pdf"',
      'X-Report-SHA256': HASH,
      'X-Report-Emission': '21',
      ...headers,
    },
  })
}

function open(role: RoleCode, path: string, routes: Parameters<typeof mockApi>[0] = {}) {
  const user = userWith(role)
  signIn(user)
  const api = mockApi({ 'GET /auth/me': [200, user], ...routes })
  return { api, ...renderApp(path) }
}

let createObjectURL: ReturnType<typeof vi.fn>

beforeEach(() => {
  // jsdom não implementa URLs de Blob nem navegação por download.
  createObjectURL = vi.fn(() => 'blob:relatorio')
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() }))
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('Prévia do relatório', () => {
  it('mostra o documento com datas no fuso do laboratório e o histórico de correções', async () => {
    open('MANAGER', '/reports/1', { 'GET /reports/samples/1': [200, REPORT] })

    const sheet = await screen.findByRole('article', { name: 'Relatório de análise SMP-2026-0001' })
    const view = within(sheet)
    expect(view.getByText('Aprovada', { selector: 'strong' })).toBeInTheDocument()
    // 14:52 UTC = 11:52 em São Paulo, como no PDF.
    expect(view.getByText('em 21/09/2026, 11:52')).toBeInTheDocument()
    expect(view.getByText('Farmacêutica Aurora (CLI-001)')).toBeInTheDocument()

    const results = view.getByRole('heading', { name: 'Resultados' }).closest('section')!
    const rows = within(results).getAllByRole('row')
    expect(rows).toHaveLength(3) // cabeçalho + pH e densidade (o cancelado fica à parte)
    expect(within(rows[1]).getByText('6,80 pH')).toBeInTheDocument()
    expect(within(rows[1]).getByText('corrigido (versão 2)')).toBeInTheDocument()
    expect(within(rows[1]).getByText('5,50 a 7,00 pH')).toBeInTheDocument()
    expect(within(rows[2]).getByText('1,0215 g/mL')).toBeInTheDocument() // nenhum dígito escondido
    expect(within(rows[2]).getByText('Equipamento DENS-01')).toBeInTheDocument()

    const corrections = view
      .getByRole('heading', { name: 'Correções de resultados' })
      .closest('section')!
    const versions = within(corrections).getAllByRole('row').slice(1)
    expect(versions).toHaveLength(2)
    expect(versions[0]).toHaveTextContent(/v1\s*7,40 pH\s*Fora da especificação/)
    expect(versions[1]).toHaveTextContent(/v2 \(vigente\)\s*6,80 pH\s*Conforme/)
    expect(within(corrections).getByText('Erro de transcrição')).toBeInTheDocument()

    const cancelled = view.getByRole('heading', { name: 'Testes cancelados' }).closest('section')!
    expect(within(cancelled).getByText('Não solicitado pelo cliente')).toBeInTheDocument()

    expect(view.getByText('Carlos Silva, equipamento DENS-01')).toBeInTheDocument()
    expect(view.getByText(HASH)).toBeInTheDocument()
  })

  it('emite o PDF, entrega o arquivo e confirma a impressão digital', async () => {
    const { api } = open('REVIEWER', '/reports/1', {
      'GET /reports/samples/1': [200, REPORT],
      'GET /reports/samples/1/pdf': () => pdfResponse(),
    })

    await userEvent.click(await screen.findByRole('button', { name: 'Emitir PDF' }))

    expect(await screen.findByText('PDF emitido (emissão nº 21)')).toBeInTheDocument()
    expect(
      screen.getByText('A impressão digital do documento confere com esta prévia.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Emissão nº 21 registrada no audit trail.')).toBeInTheDocument()
    expect(createObjectURL).toHaveBeenCalledOnce()
    const pdfCalls = api.calls.filter((call) => call.path === '/reports/samples/1/pdf')
    expect(pdfCalls).toHaveLength(1)
  })

  it('atualiza a prévia quando o PDF traz outro conteúdo', async () => {
    const { api } = open('REVIEWER', '/reports/1', {
      'GET /reports/samples/1': [200, REPORT],
      'GET /reports/samples/1/pdf': () => pdfResponse({ 'X-Report-SHA256': 'f'.repeat(64) }),
    })

    await userEvent.click(await screen.findByRole('button', { name: 'Emitir PDF' }))

    expect(
      await screen.findByText(
        'O conteúdo mudou desde que a prévia foi aberta; a prévia foi atualizada.',
      ),
    ).toBeInTheDocument()
    await waitFor(() =>
      expect(api.calls.filter((call) => call.path === '/reports/samples/1')).toHaveLength(2),
    )
  })

  it('explica quando a amostra ainda não foi revisada', async () => {
    open('ANALYST', '/reports/7', {
      'GET /reports/samples/7': [
        409,
        {
          error: {
            code: 'REPORT_NOT_AVAILABLE',
            message: 'A amostra SMP-2026-0007 ainda não tem relatório.',
            details: { status: 'IN_ANALYSIS' },
            request_id: null,
          },
        },
      ],
    })

    expect(
      await screen.findByRole('heading', { name: 'Relatório indisponível' }),
    ).toBeInTheDocument()
    expect(screen.getByText('A amostra SMP-2026-0007 ainda não tem relatório.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Abrir a amostra' })).toHaveAttribute(
      'href',
      '/samples/7',
    )
  })

  it('avisa quando a emissão falha', async () => {
    open('MANAGER', '/reports/1', {
      'GET /reports/samples/1': [200, REPORT],
      'GET /reports/samples/1/pdf': [
        409,
        {
          error: {
            code: 'REPORT_NOT_AVAILABLE',
            message: 'Relatório indisponível.',
            details: null,
            request_id: null,
          },
        },
      ],
    })

    await userEvent.click(await screen.findByRole('button', { name: 'Emitir PDF' }))

    expect(
      await screen.findByText('Não foi possível emitir o relatório SMP-2026-0001'),
    ).toBeInTheDocument()
    expect(createObjectURL).not.toHaveBeenCalled()
  })
})

describe('Lista de relatórios', () => {
  const reviewed: SampleSummary = sampleDetail({
    id: 1,
    sample_code: 'SMP-2026-0001',
    status: 'APPROVED',
  })

  it('lista só amostras revisadas e emite o PDF pela linha', async () => {
    let statuses: string[] = []
    const { api } = open('ANALYST', '/reports', {
      'GET /samples': ({ url }) => {
        statuses = url.searchParams.getAll('status')
        return [200, { ...EMPTY_PAGE, items: [reviewed], total: 1, pages: 1 }]
      },
      'GET /reports/samples/1/pdf': () => pdfResponse(),
    })

    const row = (await screen.findByText('SMP-2026-0001')).closest('tr')!
    expect(statuses).toEqual(['APPROVED', 'REJECTED'])
    expect(
      within(row).getByRole('link', { name: 'Prévia do relatório SMP-2026-0001' }),
    ).toHaveAttribute('href', '/reports/1')

    await userEvent.click(
      within(row).getByRole('button', { name: 'Emitir PDF do relatório SMP-2026-0001' }),
    )
    expect(await screen.findByText('Relatório SMP-2026-0001 emitido')).toBeInTheDocument()
    expect(api.calls.some((call) => call.path === '/reports/samples/1/pdf')).toBe(true)
  })

  it('filtra por decisão', async () => {
    const seen: string[][] = []
    open('MANAGER', '/reports?status=REJECTED', {
      'GET /samples': ({ url }) => {
        seen.push(url.searchParams.getAll('status'))
        return [200, EMPTY_PAGE]
      },
    })

    expect(await screen.findByText('Nenhuma amostra revisada encontrada')).toBeInTheDocument()
    expect(seen.at(-1)).toEqual(['REJECTED'])
  })
})

describe('Atalho no detalhe da amostra', () => {
  function openSample(role: RoleCode, sample: SampleDetail) {
    open(role, `/samples/${sample.id}`, {
      [`GET /samples/${sample.id}`]: [200, sample],
      [`GET /samples/${sample.id}/timeline`]: [200, EMPTY_PAGE],
    })
  }

  it('aparece para quem exporta relatórios, em amostra revisada', async () => {
    openSample('MANAGER', sampleDetail({ status: 'REJECTED', allowed_actions: [] }))
    expect(await screen.findByRole('link', { name: 'Relatório' })).toHaveAttribute(
      'href',
      '/reports/7',
    )
  })

  it('não aparece antes da revisão', async () => {
    openSample('MANAGER', sampleDetail({ status: 'AWAITING_REVIEW', allowed_actions: ['cancel'] }))
    expect(await screen.findByRole('button', { name: 'Cancelar amostra' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Relatório' })).not.toBeInTheDocument()
  })

  it('não aparece para o administrador (sem REPORT_EXPORT)', async () => {
    openSample('ADMIN', sampleDetail({ status: 'APPROVED', allowed_actions: [] }))
    expect(await screen.findByText('Dados da amostra')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Relatório' })).not.toBeInTheDocument()
  })
})
