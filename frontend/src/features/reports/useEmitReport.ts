import { useMutation, useQueryClient } from '@tanstack/react-query'

import { errorMessage } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import { type EmittedReport, reportsApi } from '../../api/reports'
import { useToast } from '../../components/toastContext'
import { saveFile } from '../../lib/download'

interface EmitInput {
  sampleId: number
  sampleCode: string
}

/** Emite o PDF, entrega o arquivo e atualiza o que mostra a emissão (timeline e audit). */
export function useEmitReport(onEmitted?: (report: EmittedReport, input: EmitInput) => void) {
  const queryClient = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: ({ sampleId, sampleCode }: EmitInput) => reportsApi.emitPdf(sampleId, sampleCode),
    onSuccess: (report, input) => {
      saveFile(report.blob, report.filename)
      queryClient.invalidateQueries({ queryKey: queryKeys.timeline(input.sampleId) })
      queryClient.invalidateQueries({ queryKey: ['audit'] })
      toast({
        tone: 'success',
        title: `Relatório ${input.sampleCode} emitido`,
        message:
          report.emissionId === null
            ? 'Emissão registrada no audit trail.'
            : `Emissão nº ${report.emissionId} registrada no audit trail.`,
      })
      onEmitted?.(report, input)
    },
    onError: (error, input) =>
      toast({
        tone: 'danger',
        title: `Não foi possível emitir o relatório ${input.sampleCode}`,
        message: errorMessage(error),
      }),
  })
}
