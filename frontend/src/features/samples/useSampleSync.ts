import { useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import { queryKeys } from '../../api/queryKeys'
import type { SampleDetail } from '../../types/api'

/** Depois de uma operação: atualiza o detalhe e invalida o que depende da amostra. */
export function useSampleSync(sampleId: number) {
  const queryClient = useQueryClient()
  return useCallback(
    (detail?: SampleDetail) => {
      if (detail) queryClient.setQueryData(queryKeys.sample(sampleId), detail)
      else queryClient.invalidateQueries({ queryKey: queryKeys.sample(sampleId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.timeline(sampleId) })
      queryClient.invalidateQueries({ queryKey: ['samples', 'list'] })
      queryClient.invalidateQueries({ queryKey: queryKeys.results })
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard })
    },
    [queryClient, sampleId],
  )
}
