import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeft,
  CircleCheck,
  CircleX,
  Download,
  ExternalLink,
  TriangleAlert,
} from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import type { EmittedReport } from '../../api/reports'
import { reportsApi } from '../../api/reports'
import { Alert } from '../../components/Alert'
import { SampleStatusBadge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { PageHeader } from '../../components/PageHeader'
import { ErrorState, LoadingState } from '../../components/States'
import { NotFound } from '../../components/StatusPages'
import { formatDateTimeIn, formatMeasurement, formatSpec } from '../../lib/format'
import { ORIGIN, PRIORITY } from '../../lib/labels'
import type { ReportResult, ReportTest, SampleReport } from '../../types/api'
import { useEmitReport } from './useEmitReport'

export function SampleReportPage() {
  const id = Number(useParams().sampleId)
  const report = useQuery({
    queryKey: queryKeys.sampleReport(id),
    queryFn: () => reportsApi.sample(id),
    enabled: Number.isInteger(id),
  })

  if (!Number.isInteger(id)) return <NotFound />
  if (report.isPending) return <LoadingState label="Montando o relatório…" />
  if (report.isError) {
    const error = report.error
    if (error instanceof ApiError && error.status === 404) return <NotFound />
    if (error instanceof ApiError && error.code === 'REPORT_NOT_AVAILABLE') {
      return (
        <>
          <BackLink />
          <PageHeader title="Relatório indisponível" />
          <Alert tone="info" title="A amostra ainda não foi revisada">
            {error.message}{' '}
            <Link to={`/samples/${id}`} className="with-icon">
              Abrir a amostra
            </Link>
          </Alert>
        </>
      )
    }
    return <ErrorState error={error} onRetry={() => report.refetch()} />
  }
  return <ReportView report={report.data} onStale={() => report.refetch()} />
}

function BackLink() {
  return (
    <Link to="/reports" className="back-link">
      <ArrowLeft aria-hidden /> Relatórios
    </Link>
  )
}

function ReportView({ report, onStale }: { report: SampleReport; onStale: () => void }) {
  const sample = report.sample
  const [emitted, setEmitted] = useState<EmittedReport | null>(null)
  const emit = useEmitReport((result) => {
    setEmitted(result)
    // O PDF traz o conteúdo do momento da emissão; se diferir, a prévia é atualizada.
    if (result.contentHash && result.contentHash !== report.content_hash) onStale()
  })
  const moment = (value: string | null | undefined) => formatDateTimeIn(value, report.timezone)
  const reported = report.tests.filter((test) => test.status !== 'CANCELLED')
  const corrected = report.tests.filter((test) => test.previous_versions.length > 0)
  const cancelled = report.tests.filter((test) => test.status === 'CANCELLED')
  const approved = report.decision.status === 'APPROVED'
  const performers = [
    ...report.analysts.map((user) => user.full_name),
    ...report.instruments.map((code) => `equipamento ${code}`),
  ]

  return (
    <>
      <BackLink />
      <PageHeader
        title={
          <span className="title-with-badges">
            Relatório {sample.sample_code}
            <SampleStatusBadge status={sample.status} />
          </span>
        }
        subtitle="Prévia do documento. Cada emissão do PDF fica registrada no audit trail."
        actions={
          <>
            <Link to={`/samples/${sample.id}`} className="btn btn--secondary">
              <ExternalLink aria-hidden />
              <span>Ver amostra</span>
            </Link>
            <Button
              variant="primary"
              icon={<Download aria-hidden />}
              loading={emit.isPending}
              onClick={() => emit.mutate({ sampleId: sample.id, sampleCode: sample.sample_code })}
            >
              Emitir PDF
            </Button>
          </>
        }
      />

      {emitted && (
        <Alert
          tone="success"
          title={`PDF emitido${emitted.emissionId ? ` (emissão nº ${emitted.emissionId})` : ''}`}
        >
          {emitted.contentHash === report.content_hash
            ? 'A impressão digital do documento confere com esta prévia.'
            : 'O conteúdo mudou desde que a prévia foi aberta; a prévia foi atualizada.'}
        </Alert>
      )}

      <article className="report-sheet" aria-label={`Relatório de análise ${sample.sample_code}`}>
        <header className="report-sheet__masthead">
          <div>
            <strong>LabTrack</strong>
            <span>{report.lab_name}</span>
          </div>
          <div className="report-sheet__masthead-right">
            <strong>Relatório de análise</strong>
            <span>{sample.sample_code}</span>
          </div>
        </header>

        <div className="report-sheet__title">
          <div>
            <h2>Relatório de análise</h2>
            <p>
              Amostra {sample.sample_code} · {sample.product.name} · lote {sample.lot_number}
            </p>
          </div>
          <div className={approved ? 'report-decision is-approved' : 'report-decision is-rejected'}>
            {approved ? <CircleCheck aria-hidden /> : <CircleX aria-hidden />}
            <strong>{approved ? 'Aprovada' : 'Reprovada'}</strong>
            <span>em {moment(report.decision.reviewed_at)}</span>
          </div>
        </div>

        <ReportSection title="Identificação da amostra">
          <dl className="report-facts">
            <Fact label="Cliente">
              {sample.client.name} ({sample.client.code})
            </Fact>
            <Fact label="Produto">
              {sample.product.name} ({sample.product.code})
            </Fact>
            <Fact label="Lote">{sample.lot_number}</Fact>
            <Fact label="Origem">{ORIGIN[sample.origin]}</Fact>
            <Fact label="Recebida em">{moment(sample.received_at)}</Fact>
            <Fact label="Prioridade">{PRIORITY[sample.priority].label}</Fact>
            <Fact label="Registrada por">{sample.registered_by.full_name}</Fact>
            <Fact label="Analista responsável">{sample.responsible?.full_name ?? '—'}</Fact>
            <Fact label="Enviada para revisão">{moment(sample.submitted_at)}</Fact>
            <Fact label="Categoria do produto">{sample.product.category ?? '—'}</Fact>
            {sample.notes && (
              <Fact label="Observações" wide>
                {sample.notes}
              </Fact>
            )}
          </dl>
        </ReportSection>

        <ReportSection title="Resultados">
          <div className="table-wrapper">
            <table className="table report-table">
              <thead>
                <tr>
                  <th>Teste e método</th>
                  <th>Resultado</th>
                  <th>Especificação</th>
                  <th>Situação</th>
                  <th>Registro</th>
                </tr>
              </thead>
              <tbody>
                {reported.map((test) => (
                  <tr key={test.test_code} className={isOos(test.result) ? 'is-oos' : undefined}>
                    <td>
                      <strong>{test.test_name}</strong>
                      <small>
                        {test.test_code} · {test.method}
                      </small>
                    </td>
                    <td>
                      <strong className="nowrap">{measurement(test.result, test)}</strong>
                      {test.result && test.result.version > 1 && (
                        <small>corrigido (versão {test.result.version})</small>
                      )}
                    </td>
                    <td className="nowrap">
                      {formatSpec(test.spec_min, test.spec_max, test.unit, test.decimal_places)}
                    </td>
                    <td>
                      <SpecSituation result={test.result} />
                    </td>
                    <td>{test.result ? <Recorded result={test.result} moment={moment} /> : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ReportSection>

        {corrected.length > 0 && (
          <ReportSection
            title="Correções de resultados"
            note="Toda correção gera uma nova versão com justificativa; as versões anteriores continuam registradas, inclusive as que ficaram fora da especificação."
          >
            <div className="table-wrapper">
              <table className="table report-table">
                <thead>
                  <tr>
                    <th>Teste</th>
                    <th>Versão</th>
                    <th>Valor</th>
                    <th>Situação</th>
                    <th>Registro</th>
                    <th>Justificativa da correção</th>
                  </tr>
                </thead>
                <tbody>
                  {corrected.flatMap((test) =>
                    [...test.previous_versions, ...(test.result ? [test.result] : [])].map(
                      (result) => (
                        <tr key={`${test.test_code}-${result.version}`}>
                          <td>
                            <strong>{test.test_code}</strong>
                          </td>
                          <td className="nowrap">
                            v{result.version}
                            {result === test.result && ' (vigente)'}
                          </td>
                          <td className="nowrap">{measurement(result, test)}</td>
                          <td>
                            <SpecSituation result={result} />
                          </td>
                          <td>
                            <Recorded result={result} moment={moment} />
                          </td>
                          <td>{result.change_reason ?? '—'}</td>
                        </tr>
                      ),
                    ),
                  )}
                </tbody>
              </table>
            </div>
          </ReportSection>
        )}

        {cancelled.length > 0 && (
          <ReportSection title="Testes cancelados">
            <div className="table-wrapper">
              <table className="table report-table">
                <thead>
                  <tr>
                    <th>Teste</th>
                    <th>Cancelado por</th>
                    <th>Em</th>
                    <th>Justificativa</th>
                  </tr>
                </thead>
                <tbody>
                  {cancelled.map((test) => (
                    <tr key={test.test_code}>
                      <td>
                        <strong>{test.test_name}</strong>
                        <small>{test.test_code}</small>
                      </td>
                      <td>{test.cancellation?.cancelled_by ?? '—'}</td>
                      <td className="nowrap">{moment(test.cancellation?.cancelled_at)}</td>
                      <td>{test.cancellation?.reason ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </ReportSection>
        )}

        <ReportSection title="Parecer da revisão">
          <dl className="report-facts report-facts--single">
            <Fact label="Decisão">{approved ? 'Aprovada' : 'Reprovada'}</Fact>
            <Fact label="Revisor">{report.decision.reviewed_by.full_name}</Fact>
            <Fact label="Data da decisão">{moment(report.decision.reviewed_at)}</Fact>
            <Fact label="Resultados lançados por">{performers.join(', ') || '—'}</Fact>
            <Fact label={approved ? 'Comentário da revisão' : 'Justificativa da reprovação'}>
              {report.decision.comment ?? '—'}
            </Fact>
          </dl>
          <p className="report-sheet__note">
            {approved
              ? 'Aprovação confirmada com a senha do revisor, que não lançou resultados desta amostra, e sem resultado vigente fora da especificação.'
              : 'Reprovação registrada pelo revisor com justificativa.'}
          </p>
        </ReportSection>

        <footer className="report-sheet__footer">
          <p>
            Os resultados referem-se exclusivamente à amostra analisada. Limites de especificação
            vigentes quando os testes foram atribuídos à amostra; datas e horários no fuso{' '}
            {report.timezone}.
          </p>
          <p>
            Impressão digital (SHA-256): <code className="hash">{report.content_hash}</code>
            <br />A mesma impressão digital sai no rodapé do PDF e no registro da emissão no audit
            trail.
          </p>
          <p>
            Prévia montada em {moment(report.generated_at)} para {report.generated_by.full_name}.
          </p>
        </footer>
      </article>
    </>
  )
}

function ReportSection({
  title,
  note,
  children,
}: {
  title: string
  note?: string
  children: ReactNode
}) {
  return (
    <section className="report-sheet__section">
      <h3>{title}</h3>
      {note && <p className="report-sheet__note">{note}</p>}
      {children}
    </section>
  )
}

function Fact({ label, wide, children }: { label: string; wide?: boolean; children: ReactNode }) {
  return (
    <div className={wide ? 'report-fact report-fact--wide' : 'report-fact'}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

function isOos(result: ReportResult | null): boolean {
  return result?.spec_status === 'OOS'
}

function measurement(result: ReportResult | null, test: ReportTest): string {
  return result ? formatMeasurement(result.value, result.unit, test.decimal_places) : '—'
}

function SpecSituation({ result }: { result: ReportResult | null }) {
  if (!result) return <>—</>
  if (result.spec_status === 'OOS') {
    return (
      <span className="report-oos">
        <TriangleAlert aria-hidden /> Fora da especificação
      </span>
    )
  }
  return <>Conforme</>
}

function Recorded({
  result,
  moment,
}: {
  result: ReportResult
  moment: (value: string | null | undefined) => string
}) {
  const who =
    result.source === 'INSTRUMENT'
      ? `Equipamento ${result.instrument_code ?? ''}`.trim()
      : (result.entered_by?.full_name ?? '—')
  return (
    <>
      {who}
      <small className="nowrap">{moment(result.entered_at)}</small>
    </>
  )
}
