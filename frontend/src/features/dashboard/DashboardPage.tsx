import { useQueries, useQuery } from '@tanstack/react-query'
import { TriangleAlert } from 'lucide-react'
import { Link } from 'react-router'

import { queryKeys } from '../../api/queryKeys'
import { resultsApi, samplesApi } from '../../api/samples'
import { PriorityBadge, SampleStatusBadge } from '../../components/Badge'
import { PageHeader, Panel } from '../../components/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '../../components/States'
import { formatDateTime } from '../../lib/format'
import { SAMPLE_STATUS, SAMPLE_STATUSES } from '../../lib/labels'
import type { SampleFilters } from '../../api/samples'
import { useAuth } from '../auth/authContext'

/**
 * Visão geral da ETAPA 9, montada com as consultas já existentes. Os KPIs completos
 * (tempo médio, séries mensais, gráficos) chegam com o endpoint da ETAPA 10.
 */
export function DashboardPage() {
  const { user, can } = useAuth()
  const counts = useQueries({
    queries: SAMPLE_STATUSES.map((status) => ({
      queryKey: [...queryKeys.dashboard, 'status', status],
      queryFn: () => samplesApi.search({ status: [status], size: 1 }),
      select: (page: { total: number }) => page.total,
    })),
  })
  const oos = useQuery({
    queryKey: [...queryKeys.dashboard, 'oos'],
    queryFn: () => resultsApi.search({ spec_status: 'OOS', size: 1 }),
    select: (page) => page.total,
  })

  const focus = worklistFor(user?.id, can('SAMPLE_REVIEW'), can('SAMPLE_ANALYZE'))

  return (
    <>
      <PageHeader
        title={`Olá, ${user?.full_name.split(' ')[0] ?? ''}`}
        subtitle="Situação atual das amostras do laboratório."
      />
      <div className="kpi-grid">
        {SAMPLE_STATUSES.map((status, index) => (
          <Link
            key={status}
            to={`/samples?status=${status}`}
            className={`kpi kpi--${SAMPLE_STATUS[status].tone}`}
          >
            <span>{SAMPLE_STATUS[status].label}</span>
            <strong>{counts[index].data ?? '—'}</strong>
          </Link>
        ))}
        <Link to="/results?spec_status=OOS" className="kpi kpi--danger">
          <span className="with-icon">
            <TriangleAlert aria-hidden /> Resultados OOS vigentes
          </span>
          <strong>{oos.data ?? '—'}</strong>
        </Link>
      </div>
      {focus && <FocusList title={focus.title} filters={focus.filters} link={focus.link} />}
    </>
  )
}

function worklistFor(userId: number | undefined, reviewer: boolean, analyst: boolean) {
  if (reviewer)
    return {
      title: 'Aguardando sua revisão',
      filters: { status: ['AWAITING_REVIEW'], sort: 'received_at', size: 8 } as SampleFilters,
      link: '/samples?status=AWAITING_REVIEW',
    }
  if (analyst && userId)
    return {
      title: 'Suas amostras em andamento',
      filters: {
        status: ['RECEIVED', 'IN_ANALYSIS'],
        responsible_id: userId,
        sort: '-priority',
        size: 8,
      } as SampleFilters,
      link: '/samples?status=RECEIVED&status=IN_ANALYSIS&mine=1',
    }
  return {
    title: 'Recebidas recentemente',
    filters: { sort: '-received_at', size: 8 } as SampleFilters,
    link: '/samples',
  }
}

function FocusList({
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
