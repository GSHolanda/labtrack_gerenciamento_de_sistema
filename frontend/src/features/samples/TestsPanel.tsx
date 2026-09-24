import { Clock, Cpu, Pencil, Plus, TriangleAlert, UserRound, X } from 'lucide-react'
import { useState } from 'react'

import { samplesApi } from '../../api/samples'
import { SpecBadge, TestStatusBadge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Panel } from '../../components/PageHeader'
import { ReasonDialog } from '../../components/ReasonDialog'
import { EmptyState } from '../../components/States'
import { useToast } from '../../components/toastContext'
import { formatDateTime, formatMeasurement, formatSpec } from '../../lib/format'
import type { ResultRead, SampleDetail, SampleTest } from '../../types/api'
import { useAuth } from '../auth/authContext'
import { AssignTestsDialog } from './AssignTestsDialog'
import { ResultDialog } from './ResultDialog'
import { ResultHistoryDialog } from './ResultHistoryDialog'
import { useSampleSync } from './useSampleSync'

type Dialog =
  | { kind: 'result' | 'history' | 'cancel'; test: SampleTest }
  | { kind: 'assign' }
  | null

const EDITABLE = new Set(['RECEIVED', 'IN_ANALYSIS'])

export function TestsPanel({ sample }: { sample: SampleDetail }) {
  const { can } = useAuth()
  const toast = useToast()
  const sync = useSampleSync(sample.id)
  const [dialog, setDialog] = useState<Dialog>(null)

  const inAnalysis = sample.status === 'IN_ANALYSIS'
  const canEnter = can('RESULT_ENTER') && inAnalysis
  const canAssign = can('SAMPLE_ASSIGN_TESTS') && EDITABLE.has(sample.status)

  function resultSaved(test: SampleTest, result: ResultRead) {
    sync()
    toast({
      tone: result.spec_status === 'OOS' ? 'danger' : 'success',
      title:
        result.spec_status === 'OOS'
          ? `${test.test_name}: resultado fora da especificação`
          : `${test.test_name}: resultado registrado`,
      message: `${formatMeasurement(result.value, result.unit, test.decimal_places)} (versão ${result.version})`,
    })
  }

  return (
    <Panel
      title="Testes e resultados"
      actions={
        canAssign && (
          <Button size="sm" icon={<Plus aria-hidden />} onClick={() => setDialog({ kind: 'assign' })}>
            Atribuir testes
          </Button>
        )
      }
    >
      {sample.tests.length === 0 ? (
        <EmptyState title="Nenhum teste atribuído">
          A análise só pode começar com pelo menos um teste.
        </EmptyState>
      ) : (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Teste</th>
                <th>Especificação</th>
                <th>Resultado</th>
                <th>Status</th>
                <th aria-label="Ações" />
              </tr>
            </thead>
            <tbody>
              {sample.tests.map((test) => {
                const result = test.current_result
                const cancelled = test.status === 'CANCELLED'
                const oos = result?.spec_status === 'OOS' && !cancelled
                return (
                  <tr
                    key={test.id}
                    className={oos ? 'row--oos' : cancelled ? 'row--muted' : undefined}
                  >
                    <td>
                      <div className="cell-stack">
                        <strong>{test.test_name}</strong>
                        <small>
                          <code>{test.test_code}</code> · {test.method}
                        </small>
                      </div>
                    </td>
                    <td className="nowrap">
                      {formatSpec(test.spec_min, test.spec_max, test.unit, test.decimal_places)}
                    </td>
                    <td>
                      {result ? (
                        <div className="cell-stack">
                          <span className="result-value">
                            <strong>
                              {formatMeasurement(result.value, result.unit, test.decimal_places)}
                            </strong>
                            <SpecBadge status={result.spec_status} short />
                          </span>
                          <small className="with-icon">
                            {result.instrument_code ? (
                              <>
                                <Cpu aria-hidden /> {result.instrument_code}
                              </>
                            ) : (
                              <>
                                <UserRound aria-hidden /> {result.entered_by?.full_name}
                              </>
                            )}
                            {' · '}
                            {formatDateTime(result.entered_at)}
                          </small>
                          {(test.result_versions > 1 || test.had_oos) && (
                            <small className="result-flags">
                              {test.result_versions > 1 && (
                                <span>Corrigido ({test.result_versions} versões)</span>
                              )}
                              {test.had_oos && result.spec_status !== 'OOS' && (
                                <span className="text-danger with-icon">
                                  <TriangleAlert aria-hidden /> Houve OOS
                                </span>
                              )}
                            </small>
                          )}
                        </div>
                      ) : (
                        <span className="muted">Aguardando resultado</span>
                      )}
                    </td>
                    <td>
                      <TestStatusBadge status={test.status} />
                    </td>
                    <td>
                      <div className="row-actions">
                        {canEnter && !cancelled && (
                          <Button
                            size="sm"
                            variant={result ? 'secondary' : 'primary'}
                            icon={result ? <Pencil aria-hidden /> : <Plus aria-hidden />}
                            onClick={() => setDialog({ kind: 'result', test })}
                          >
                            {result ? 'Corrigir' : 'Lançar'}
                          </Button>
                        )}
                        {test.result_versions > 0 && (
                          <Button
                            size="sm"
                            variant="ghost"
                            icon={<Clock aria-hidden />}
                            onClick={() => setDialog({ kind: 'history', test })}
                          >
                            Histórico
                          </Button>
                        )}
                        {canAssign && test.status === 'PENDING' && (
                          <Button
                            size="sm"
                            variant="ghost"
                            icon={<X aria-hidden />}
                            onClick={() => setDialog({ kind: 'cancel', test })}
                          >
                            Cancelar
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {dialog?.kind === 'assign' && (
        <AssignTestsDialog
          sample={sample}
          onClose={() => setDialog(null)}
          onSaved={(updated) => {
            sync(updated)
            toast({ title: 'Testes atribuídos' })
          }}
        />
      )}
      {dialog?.kind === 'result' && (
        <ResultDialog
          sampleTest={dialog.test}
          onClose={() => setDialog(null)}
          onSaved={(result) => resultSaved(dialog.test, result)}
        />
      )}
      {dialog?.kind === 'history' && (
        <ResultHistoryDialog sampleTest={dialog.test} onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === 'cancel' && (
        <ReasonDialog
          title={`Cancelar o teste ${dialog.test.test_name}`}
          description="Apenas testes pendentes podem ser cancelados."
          confirmLabel="Cancelar teste"
          danger
          onClose={() => setDialog(null)}
          onConfirm={async (reason) => {
            sync(await samplesApi.cancelTest(dialog.test.id, reason))
            toast({ title: `Teste ${dialog.test.test_name} cancelado` })
          }}
        />
      )}
    </Panel>
  )
}
