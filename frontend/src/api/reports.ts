import type { SampleReport } from '../types/api'
import { http } from './client'

export interface EmittedReport {
  blob: Blob
  filename: string
  contentHash: string | null
  emissionId: number | null
}

export const reportsApi = {
  /** Prévia: conteúdo do relatório, sem registro no audit trail. */
  sample: (sampleId: number) => http.get<SampleReport>(`/reports/samples/${sampleId}`),

  /** Emite o PDF: cada chamada gera um registro REPORT_GENERATED no audit trail. */
  async emitPdf(sampleId: number, sampleCode: string): Promise<EmittedReport> {
    const file = await http.download(`/reports/samples/${sampleId}/pdf`, 'application/pdf')
    const emission = file.headers.get('X-Report-Emission')
    return {
      blob: file.blob,
      filename: file.filename ?? `relatorio-${sampleCode}.pdf`,
      contentHash: file.headers.get('X-Report-SHA256'),
      emissionId: emission ? Number(emission) : null,
    }
  },
}
