import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'

import { queryKeys } from '../../api/queryKeys'
import { samplesApi } from '../../api/samples'
import { Alert } from '../../components/Alert'
import { SampleStatusBadge } from '../../components/Badge'
import { PageHeader } from '../../components/PageHeader'
import { Pagination } from '../../components/Pagination'
import { EmptyState, ErrorState, LoadingState } from '../../components/States'
import { useListParams } from '../../hooks/useListParams'
import { formatDateTime } from '../../lib/format'
import type { SampleFilters } from '../../api/samples'

/** Amostras finalizadas, candidatas a relatório. O PDF chega na ETAPA 11. */
export function ReportsPage() {
  const list = useListParams()
  const filters: SampleFilters = {
    status: ['APPROVED', 'REJECTED'],
    sort: '-received_at',
    page: list.page,
    size: 20,
  }
  const query = useQuery({
    queryKey: queryKeys.sampleList(filters),
    queryFn: () => samplesApi.search(filters),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <PageHeader
        title="Relatórios"
        subtitle="Relatórios de análise das amostras finalizadas."
      />
      <Alert tone="info" title="Relatório em PDF na ETAPA 11">
        A geração do relatório da amostra (JSON e PDF, registrada no audit trail) faz parte da
        próxima etapa do roadmap. Enquanto isso, os dados completos de cada amostra estão no
        detalhe.
      </Alert>
      <section className="panel">
        {query.isPending ? (
          <LoadingState />
        ) : query.isError ? (
          <ErrorState error={query.error} />
        ) : query.data.items.length === 0 ? (
          <EmptyState title="Nenhuma amostra finalizada" />
        ) : (
          <>
            <div className="table-wrapper">
              <table className="table">
                <thead>
                  <tr>
                    <th>Amostra</th>
                    <th>Produto</th>
                    <th>Cliente</th>
                    <th>Lote</th>
                    <th>Recebida em</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((sample) => (
                    <tr key={sample.id}>
                      <td>
                        <Link to={`/samples/${sample.id}`} className="code-link">
                          {sample.sample_code}
                        </Link>
                      </td>
                      <td>{sample.product.name}</td>
                      <td>{sample.client.name}</td>
                      <td>{sample.lot_number}</td>
                      <td className="nowrap">{formatDateTime(sample.received_at)}</td>
                      <td>
                        <SampleStatusBadge status={sample.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={query.data.page}
              pages={query.data.pages}
              total={query.data.total}
              size={query.data.size}
              onPage={list.setPage}
            />
          </>
        )}
      </section>
    </>
  )
}
