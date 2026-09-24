import { useQuery } from '@tanstack/react-query'
import { TriangleAlert } from 'lucide-react'
import { Link } from 'react-router'

import { queryKeys } from '../../api/queryKeys'
import { type SampleFilters, samplesApi } from '../../api/samples'
import { PriorityBadge, SampleStatusBadge } from '../../components/Badge'
import { Panel } from '../../components/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '../../components/States'
import { formatDateTime } from '../../lib/format'

export function FocusList({
  title,
  filters,
  link,
}: {
  title: string
  filters: SampleFilters
  link: string
}) {
  const query = useQuery({
    queryKey: [...queryKeys.dashboard, 'focus', filters],
    queryFn: () => samplesApi.search(filters),
  })
  return (
    <Panel
      title={title}
      actions={
        <Link to={link} className="small-link">
          Ver todas
        </Link>
      }
    >
      {query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState error={query.error} />
      ) : query.data.items.length === 0 ? (
        <EmptyState title="Nada pendente por aqui" />
      ) : (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Amostra</th>
                <th>Produto</th>
                <th>Recebida em</th>
                <th>Prioridade</th>
                <th>Status</th>
                <th>Testes</th>
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((sample) => (
                <tr key={sample.id}>
                  <td>
                    <Link to={`/samples/${sample.id}`} className="code-link">
                      {sample.sample_code}
                    </Link>
                    {sample.has_oos && (
                      <span className="oos-flag">
                        <TriangleAlert aria-hidden /> OOS
                      </span>
                    )}
                  </td>
                  <td>{sample.product.name}</td>
                  <td className="nowrap">{formatDateTime(sample.received_at)}</td>
                  <td>
                    <PriorityBadge priority={sample.priority} />
                  </td>
                  <td>
                    <SampleStatusBadge status={sample.status} />
                  </td>
                  <td>
                    {sample.tests_completed}/{sample.tests_total}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  )
}
