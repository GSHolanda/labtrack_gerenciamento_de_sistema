import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Check, Clock, TriangleAlert } from 'lucide-react'
import { Suspense, lazy } from 'react'
import { useSearchParams } from 'react-router'

import { dashboardApi } from '../../api/dashboard'
import { queryKeys } from '../../api/queryKeys'
import { PageHeader } from '../../components/PageHeader'
import { ErrorState, LoadingState } from '../../components/States'
import { formatDateTime } from '../../lib/format'
import type { DashboardSummary } from '../../types/api'
import { useAuth } from '../auth/authContext'
import { FocusList } from './FocusList'
import { StatTile } from './StatTile'
import { delta, formatCount, formatHours, formatPercent } from './dashboardFormat'
import { worklistFor } from './worklist'

// Recharts só é baixado quando o dashboard abre (a tela de login não paga por ele).
const DashboardCharts = lazy(() => import('./DashboardCharts'))

const PERIODS = [
  { days: 7, label: '7 dias', comparison: 'vs. 7 dias anteriores' },
  { days: 30, label: '30 dias', comparison: 'vs. 30 dias anteriores' },
  { days: 90, label: '90 dias', comparison: 'vs. 90 dias anteriores' },
  { days: 365, label: '12 meses', comparison: 'vs. 12 meses anteriores' },
] as const
const DEFAULT_DAYS = 90

const OPEN_LINK = '/samples?status=RECEIVED&status=IN_ANALYSIS&status=AWAITING_REVIEW'

export function DashboardPage() {
  const { user, can } = useAuth()
  const [params, setParams] = useSearchParams()
  const period = PERIODS.find((item) => String(item.days) === params.get('period'))
    ?? PERIODS.find((item) => item.days === DEFAULT_DAYS)!

  const summary = useQuery({
    queryKey: queryKeys.dashboardSummary(period.days),
    queryFn: () => dashboardApi.summary(period.days),
    placeholderData: keepPreviousData,
  })
  const charts = useQuery({
    queryKey: queryKeys.dashboardCharts(period.days),
    queryFn: () => dashboardApi.charts(period.days),
    placeholderData: keepPreviousData,
  })
  const focus = worklistFor(user?.id, can('SAMPLE_REVIEW'), can('SAMPLE_ANALYZE'))

  return (
    <>
      <PageHeader
        title={`Olá, ${user?.full_name.split(' ')[0] ?? ''}`}
        subtitle={
          summary.data
            ? `Indicadores do laboratório, atualizados em ${formatDateTime(summary.data.generated_at)}.`
            : 'Indicadores do laboratório.'
        }
      />

      {summary.isPending ? (
        <LoadingState />
      ) : summary.isError ? (
        <ErrorState error={summary.error} onRetry={() => summary.refetch()} />
      ) : (
        <Workload summary={summary.data} />
      )}

      <div className="period-bar" role="group" aria-label="Período dos indicadores e gráficos">
        <span className="period-bar__label">Período</span>
        <div className="segmented">
          {PERIODS.map((item) => (
            <button
              key={item.days}
              type="button"
              className={item.days === period.days ? 'segmented__option is-active' : 'segmented__option'}
              aria-pressed={item.days === period.days}
              onClick={() => setParams({ period: String(item.days) }, { replace: true })}
            >
              {item.days === period.days && <Check aria-hidden />}
              {item.label}
            </button>
          ))}
        </div>
        <span className="period-bar__note">
          Tudo abaixo considera os últimos {period.label} até agora, no fuso do laboratório.
        </span>
      </div>

      <div className={summary.isPlaceholderData || charts.isPlaceholderData ? 'is-refreshing' : undefined}>
        {summary.data && (
          <PeriodTiles summary={summary.data} comparison={period.comparison} />
        )}
        {charts.isPending ? (
          <LoadingState label="Carregando gráficos…" />
        ) : charts.isError ? (
          <ErrorState error={charts.error} onRetry={() => charts.refetch()} />
        ) : (
          <Suspense fallback={<LoadingState label="Carregando gráficos…" />}>
            <DashboardCharts charts={charts.data} />
          </Suspense>
        )}
      </div>

      <FocusList title={focus.title} filters={focus.filters} link={focus.link} />
    </>
  )
}

function Workload({ summary }: { summary: DashboardSummary }) {
  const workload = summary.workload
  return (
    <section className="dashboard-section" aria-labelledby="agora">
      <h2 id="agora" className="section-title">
        Agora
      </h2>
      <div className="stat-grid">
        <StatTile label="Em aberto" value={formatCount(workload.open)} to={OPEN_LINK} />
        <StatTile
          label="Aguardando início"
          value={formatCount(workload.received)}
          to="/samples?status=RECEIVED"
        />
        <StatTile
          label="Em análise"
          value={formatCount(workload.in_analysis)}
          to="/samples?status=IN_ANALYSIS"
        />
        <StatTile
          label="Aguardando revisão"
          value={formatCount(workload.awaiting_review)}
          to="/samples?status=AWAITING_REVIEW"
        />
        <StatTile
          label="Em aberto com OOS vigente"
          value={formatCount(workload.open_with_oos)}
          hint="Bloqueiam a aprovação"
          alert={workload.open_with_oos > 0}
          icon={workload.open_with_oos > 0 ? <TriangleAlert aria-hidden /> : undefined}
        />
        <StatTile
          label="Urgentes em aberto"
          value={formatCount(workload.urgent_open)}
          to={`${OPEN_LINK}&priority=URGENT`}
        />
      </div>
    </section>
  )
}

function PeriodTiles({ summary, comparison }: { summary: DashboardSummary; comparison: string }) {
  const { current, previous } = summary
  return (
    <section className="dashboard-section" aria-label="Indicadores do período">
      <div className="stat-grid">
        <StatTile
          label="Recebidas"
          value={formatCount(current.received)}
          delta={delta(current.received, previous.received, 'none')}
          comparison={comparison}
        />
        <StatTile
          label="Aprovadas"
          value={formatCount(current.approved)}
          delta={delta(current.approved, previous.approved, 'up')}
          comparison={comparison}
        />
        <StatTile
          label="Reprovadas"
          value={formatCount(current.rejected)}
          delta={delta(current.rejected, previous.rejected, 'down')}
          comparison={comparison}
        />
        <StatTile
          label="Taxa de aprovação"
          value={formatPercent(current.approval_rate)}
          delta={delta(current.approval_rate, previous.approval_rate, 'up', 'rate')}
          comparison={comparison}
          hint="Aprovadas sobre decididas (sem canceladas)"
        />
        <StatTile
          label="Tempo até a decisão"
          icon={<Clock aria-hidden />}
          value={formatHours(current.average_processing_hours)}
          delta={delta(
            current.average_processing_hours,
            previous.average_processing_hours,
            'down',
            'hours',
          )}
          comparison={comparison}
          hint={
            current.median_processing_hours === null
              ? 'Média do recebimento à aprovação ou reprovação'
              : `Média; mediana ${formatHours(current.median_processing_hours)}`
          }
        />
        <StatTile
          label="Resultados OOS"
          value={formatCount(current.oos_results)}
          delta={delta(current.oos_results, previous.oos_results, 'down')}
          comparison={comparison}
          hint={`Em ${formatCount(current.samples_with_oos)} amostra(s), inclusive os corrigidos`}
          to="/results?spec_status=OOS&history=1"
        />
      </div>
    </section>
  )
}
