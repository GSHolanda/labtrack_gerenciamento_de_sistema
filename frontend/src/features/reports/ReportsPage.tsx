import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Download, FileText } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { queryKeys } from '../../api/queryKeys'
import type { SampleFilters } from '../../api/samples'
import { samplesApi } from '../../api/samples'
import { SampleStatusBadge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { SelectField, TextField } from '../../components/Field'
import { PageHeader } from '../../components/PageHeader'
import { Pagination } from '../../components/Pagination'
import { EmptyState, ErrorState, LoadingState } from '../../components/States'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { useListParams } from '../../hooks/useListParams'
import { formatDateTime } from '../../lib/format'
import type { SampleStatus } from '../../types/api'
import { useEmitReport } from './useEmitReport'

// RN-27: relatório só para amostras revisadas (aprovadas ou reprovadas).
const REPORTABLE: SampleStatus[] = ['APPROVED', 'REJECTED']

export function ReportsPage() {
  const list = useListParams()
  const [search, setSearch] = useState(list.get('q'))
  const debouncedSearch = useDebouncedValue(search)
  const emit = useEmitReport()

  useEffect(() => {
    if (debouncedSearch !== list.get('q')) list.update({ q: debouncedSearch })
  }, [debouncedSearch, list])

  const decision = list.get('status') as SampleStatus | ''
  const filters: SampleFilters = {
    q: list.get('q') || undefined,
    status: decision && REPORTABLE.includes(decision) ? [decision] : REPORTABLE,
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
        subtitle="Relatório de análise das amostras aprovadas ou reprovadas. Cada emissão em PDF fica registrada no audit trail."
      />

      <section className="filters" aria-label="Filtros">
        <div className="filters__row">
          <TextField
            label="Busca"
            type="search"
            placeholder="Código, lote, produto ou cliente"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <SelectField
            label="Decisão"
            value={decision}
            onChange={(event) => list.update({ status: event.target.value })}
          >
            <option value="">Aprovadas e reprovadas</option>
            <option value="APPROVED">Aprovadas</option>
            <option value="REJECTED">Reprovadas</option>
          </SelectField>
        </div>
      </section>

      <section className="panel">
        {query.isPending ? (
          <LoadingState />
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        ) : query.data.items.length === 0 ? (
          <EmptyState title="Nenhuma amostra revisada encontrada">
            O relatório fica disponível depois da aprovação ou reprovação da amostra.
          </EmptyState>
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
                    <th>Decisão</th>
                    <th>
                      <span className="sr-only">Ações</span>
                    </th>
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
                      <td>
                        <div className="row-actions">
                          <Link
                            to={`/reports/${sample.id}`}
                            className="btn btn--ghost btn--sm"
                            aria-label={`Prévia do relatório ${sample.sample_code}`}
                          >
                            <FileText aria-hidden />
                            <span>Prévia</span>
                          </Link>
                          <Button
                            size="sm"
                            icon={<Download aria-hidden />}
                            aria-label={`Emitir PDF do relatório ${sample.sample_code}`}
                            loading={emit.isPending && emit.variables?.sampleId === sample.id}
                            disabled={emit.isPending}
                            onClick={() =>
                              emit.mutate({ sampleId: sample.id, sampleCode: sample.sample_code })
                            }
                          >
                            PDF
                          </Button>
                        </div>
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
