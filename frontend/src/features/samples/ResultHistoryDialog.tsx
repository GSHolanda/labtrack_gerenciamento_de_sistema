import { useQuery } from '@tanstack/react-query'
import { Cpu, UserRound } from 'lucide-react'

import { queryKeys } from '../../api/queryKeys'
import { resultsApi } from '../../api/samples'
import { SpecBadge } from '../../components/Badge'
import { Modal } from '../../components/Modal'
import { ErrorState, LoadingState } from '../../components/States'
import { formatDateTime, formatMeasurement } from '../../lib/format'
import type { SampleTest } from '../../types/api'

/** Todas as versões do resultado: nada é sobrescrito (RN-17 e RN-18). */
export function ResultHistoryDialog({
  sampleTest,
  onClose,
}: {
  sampleTest: SampleTest
  onClose: () => void
}) {
  const history = useQuery({
    queryKey: queryKeys.resultHistory(sampleTest.id),
    queryFn: () => resultsApi.history(sampleTest.id),
  })

  return (
    <Modal title={`Histórico: ${sampleTest.test_name}`} onClose={onClose} size="lg">
      {history.isPending ? (
        <LoadingState />
      ) : history.isError ? (
        <ErrorState error={history.error} />
      ) : (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Versão</th>
                <th>Valor</th>
                <th>Situação</th>
                <th>Origem</th>
                <th>Registrado em</th>
                <th>Justificativa / comentário</th>
              </tr>
            </thead>
            <tbody>
              {history.data.map((result) => (
                <tr key={result.id} className={result.is_current ? 'row--current' : undefined}>
                  <td>
                    v{result.version}
                    {result.is_current && <small className="muted"> (vigente)</small>}
                  </td>
                  <td className="nowrap">
                    {formatMeasurement(result.value, result.unit, sampleTest.decimal_places)}
                  </td>
                  <td>
                    <SpecBadge status={result.spec_status} short />
                  </td>
                  <td>
                    <span className="with-icon">
                      {result.instrument_code ? (
                        <>
                          <Cpu aria-hidden /> {result.instrument_code}
                        </>
                      ) : (
                        <>
                          <UserRound aria-hidden /> {result.entered_by?.full_name}
                        </>
                      )}
                    </span>
                  </td>
                  <td className="nowrap">{formatDateTime(result.entered_at)}</td>
                  <td>
                    {result.change_reason && <p>{result.change_reason}</p>}
                    {result.comment && <p className="muted">{result.comment}</p>}
                    {!result.change_reason && !result.comment && '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  )
}
