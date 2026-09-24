import { Ban, CircleCheck, CircleX, Pencil, Play, Send, Undo2 } from 'lucide-react'
import { type ReactNode, useState } from 'react'

import { type ActionPayload, samplesApi } from '../../api/samples'
import { Button } from '../../components/Button'
import { ReasonDialog } from '../../components/ReasonDialog'
import { useToast } from '../../components/toastContext'
import { SAMPLE_ACTION } from '../../lib/labels'
import type { Permission, SampleAction, SampleDetail } from '../../types/api'
import { useAuth } from '../auth/authContext'
import { ApproveDialog } from './ApproveDialog'
import { SampleFormDialog } from './SampleFormDialog'
import { useSampleSync } from './useSampleSync'

// Quem executa cada ação (docs/api.md); o botão só aparece para quem pode.
const ACTION_PERMISSION: Record<SampleAction, Permission> = {
  start_analysis: 'SAMPLE_ANALYZE',
  submit_for_review: 'SAMPLE_ANALYZE',
  approve: 'SAMPLE_REVIEW',
  reject: 'SAMPLE_REVIEW',
  return_to_analysis: 'SAMPLE_REVIEW',
  cancel: 'SAMPLE_CANCEL',
}

const ACTION_ICON: Record<SampleAction, ReactNode> = {
  start_analysis: <Play aria-hidden />,
  submit_for_review: <Send aria-hidden />,
  approve: <CircleCheck aria-hidden />,
  reject: <CircleX aria-hidden />,
  return_to_analysis: <Undo2 aria-hidden />,
  cancel: <Ban aria-hidden />,
}

const EDITABLE = new Set(['RECEIVED', 'IN_ANALYSIS'])

type Dialog = 'approve' | 'reject' | 'return_to_analysis' | 'cancel' | 'edit' | null

export function SampleActions({ sample }: { sample: SampleDetail }) {
  const { can } = useAuth()
  const toast = useToast()
  const sync = useSampleSync(sample.id)
  const [dialog, setDialog] = useState<Dialog>(null)
  const [running, setRunning] = useState<SampleAction | null>(null)

  const available = sample.allowed_actions.filter((action) => can(ACTION_PERMISSION[action]))
  const pendingTests = sample.tests_total - sample.tests_completed
  const hasOos = sample.oos_tests.length > 0

  async function run(action: SampleAction, payload?: ActionPayload) {
    const updated = await samplesApi.act(sample.id, action, payload)
    sync(updated)
    toast({ title: `${SAMPLE_ACTION[action]}: ${sample.sample_code}` })
    return updated
  }

  async function runDirect(action: SampleAction) {
    setRunning(action)
    try {
      await run(action)
    } catch (error) {
      toast({
        tone: 'danger',
        title: `Não foi possível ${SAMPLE_ACTION[action].toLowerCase()}`,
        message: error instanceof Error ? error.message : undefined,
      })
    } finally {
      setRunning(null)
    }
  }

  const disabledReason = (action: SampleAction): string | undefined => {
    if (action === 'submit_for_review' && pendingTests > 0)
      return `Existem ${pendingTests} teste(s) sem resultado.`
    if (action === 'approve' && hasOos)
      return `Resultado fora da especificação: ${sample.oos_tests.join(', ')}.`
    return undefined
  }

  const variant = (action: SampleAction) =>
    action === 'approve'
      ? 'success'
      : action === 'reject' || action === 'cancel'
        ? 'danger'
        : action === 'return_to_analysis'
          ? 'secondary'
          : 'primary'

  return (
    <>
      <div className="action-bar">
        {can('SAMPLE_CREATE') && EDITABLE.has(sample.status) && (
          <Button icon={<Pencil aria-hidden />} onClick={() => setDialog('edit')}>
            Editar dados
          </Button>
        )}
        {available.map((action) => {
          const reason = disabledReason(action)
          return (
            <Button
              key={action}
              variant={variant(action)}
              icon={ACTION_ICON[action]}
              loading={running === action}
              disabled={reason !== undefined || running !== null}
              title={reason}
              onClick={() =>
                action === 'start_analysis' || action === 'submit_for_review'
                  ? runDirect(action)
                  : setDialog(action)
              }
            >
              {SAMPLE_ACTION[action]}
            </Button>
          )
        })}
      </div>

      {dialog === 'edit' && (
        <SampleFormDialog sample={sample} onClose={() => setDialog(null)} onSaved={sync} />
      )}
      {dialog === 'approve' && (
        <ApproveDialog
          sampleCode={sample.sample_code}
          onClose={() => setDialog(null)}
          onConfirm={(password, comment) => run('approve', { password, comment })}
        />
      )}
      {dialog === 'reject' && (
        <ReasonDialog
          title={`Reprovar ${sample.sample_code}`}
          description="A reprovação é final: a amostra não poderá mais ser alterada."
          confirmLabel="Reprovar amostra"
          danger
          onClose={() => setDialog(null)}
          onConfirm={(reason) => run('reject', { reason })}
        />
      )}
      {dialog === 'return_to_analysis' && (
        <ReasonDialog
          title={`Devolver ${sample.sample_code} para análise`}
          description="O analista poderá corrigir resultados e enviar a amostra novamente."
          confirmLabel="Devolver para análise"
          onClose={() => setDialog(null)}
          onConfirm={(reason) => run('return_to_analysis', { reason })}
        />
      )}
      {dialog === 'cancel' && (
        <ReasonDialog
          title={`Cancelar ${sample.sample_code}`}
          description="O cancelamento é final e invalida o registro da amostra."
          confirmLabel="Cancelar amostra"
          danger
          onClose={() => setDialog(null)}
          onConfirm={(reason) => run('cancel', { reason })}
        />
      )}
    </>
  )
}
