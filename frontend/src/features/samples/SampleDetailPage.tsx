import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, ShieldCheck } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import { samplesApi } from '../../api/samples'
import { Alert } from '../../components/Alert'
import { PriorityBadge, SampleStatusBadge } from '../../components/Badge'
import { PageHeader, Panel } from '../../components/PageHeader'
import { ErrorState, LoadingState } from '../../components/States'
import { NotFound } from '../../components/StatusPages'
import { formatDateTime } from '../../lib/format'
import { ORIGIN } from '../../lib/labels'
import type { SampleDetail } from '../../types/api'
import { useAuth } from '../auth/authContext'
import { SampleActions } from './SampleActions'
import { SampleTimeline } from './SampleTimeline'
import { TestsPanel } from './TestsPanel'

export function SampleDetailPage() {
  const id = Number(useParams().sampleId)
  const sample = useQuery({
    queryKey: queryKeys.sample(id),
    queryFn: () => samplesApi.get(id),
    enabled: Number.isInteger(id),
  })

  if (!Number.isInteger(id)) return <NotFound />
  if (sample.isPending) return <LoadingState />
  if (sample.isError) {
    if (sample.error instanceof ApiError && sample.error.status === 404) return <NotFound />
    return <ErrorState error={sample.error} onRetry={() => sample.refetch()} />
  }
  return <SampleDetailView sample={sample.data} />
}

function SampleDetailView({ sample }: { sample: SampleDetail }) {
  const { can } = useAuth()
  const correctedOos = sample.tests
    .filter((test) => test.had_oos && test.current_result?.spec_status !== 'OOS')
    .map((test) => test.test_code)

  return (
    <>
      <Link to="/samples" className="back-link">
        <ArrowLeft aria-hidden /> Amostras
      </Link>
      <PageHeader
        title={
          <span className="title-with-badges">
            {sample.sample_code}
            <SampleStatusBadge status={sample.status} />
            <PriorityBadge priority={sample.priority} />
          </span>
        }
        subtitle={`${sample.product.name} · ${sample.client.name} · lote ${sample.lot_number}`}
        actions={<SampleActions sample={sample} />}
      />

      <div className="stack">
        {sample.oos_tests.length > 0 && (
          <Alert tone="danger" title="Resultado fora da especificação (OOS)">
            {sample.oos_tests.join(', ')}. A amostra não pode ser aprovada enquanto houver
            resultado vigente fora da especificação.
          </Alert>
        )}
        {correctedOos.length > 0 && (
          <Alert tone="warning" title="Histórico de OOS">
            {correctedOos.join(', ')} teve resultado fora da especificação, depois corrigido. As
            versões anteriores continuam no histórico do teste e na timeline.
          </Alert>
        )}
        <FinalStatusNotice sample={sample} />
      </div>

      <div className="detail-grid">
        <div className="stack">
          <Panel
            title="Dados da amostra"
            actions={
              can('AUDIT_READ') && (
                <Link to={`/audit?sample_id=${sample.id}`} className="with-icon small-link">
                  <ShieldCheck aria-hidden /> Ver no audit trail
                </Link>
              )
            }
          >
            <dl className="facts">
              <Fact label="Produto">
                {sample.product.name} <code>{sample.product.code}</code>
              </Fact>
              <Fact label="Cliente">{sample.client.name}</Fact>
              <Fact label="Lote">{sample.lot_number}</Fact>
              <Fact label="Origem">{ORIGIN[sample.origin]}</Fact>
              <Fact label="Recebida em">{formatDateTime(sample.received_at)}</Fact>
              <Fact label="Registrada por">
                {sample.created_by.full_name} em {formatDateTime(sample.created_at)}
              </Fact>
              <Fact label="Responsável">{sample.responsible?.full_name ?? '—'}</Fact>
              <Fact label="Progresso">
                {sample.tests_completed} de {sample.tests_total} testes concluídos
              </Fact>
              {sample.submitted_at && (
                <Fact label="Enviada para revisão">{formatDateTime(sample.submitted_at)}</Fact>
              )}
              {sample.notes && (
                <Fact label="Observações" wide>
                  {sample.notes}
                </Fact>
              )}
            </dl>
          </Panel>
          <TestsPanel sample={sample} />
        </div>
        <Panel title="Sample Timeline" className="panel--timeline">
          <SampleTimeline sampleId={sample.id} />
        </Panel>
      </div>
    </>
  )
}

function FinalStatusNotice({ sample }: { sample: SampleDetail }) {
  const reviewer = sample.reviewed_by?.full_name
  const when = formatDateTime(sample.reviewed_at ?? sample.completed_at)
  if (sample.status === 'APPROVED')
    return (
      <Alert tone="success" title={`Aprovada por ${reviewer} em ${when}`}>
        {sample.review_comment}
      </Alert>
    )
  if (sample.status === 'REJECTED')
    return (
      <Alert tone="danger" title={`Reprovada por ${reviewer} em ${when}`}>
        {sample.review_comment}
      </Alert>
    )
  if (sample.status === 'CANCELLED')
    return (
      <Alert tone="info" title={`Amostra cancelada em ${formatDateTime(sample.completed_at)}`}>
        O motivo está registrado na timeline.
      </Alert>
    )
  return null
}

function Fact({
  label,
  children,
  wide = false,
}: {
  label: string
  children: ReactNode
  wide?: boolean
}) {
  return (
    <div className={wide ? 'facts__item facts__item--wide' : 'facts__item'}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}
