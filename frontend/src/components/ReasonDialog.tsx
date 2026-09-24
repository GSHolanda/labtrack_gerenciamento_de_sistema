import { type FormEvent, useState } from 'react'

import { Button } from './Button'
import { TextAreaField } from './Field'
import { Modal } from './Modal'
import { InlineError } from './States'

const MIN_LENGTH = 5

/** Justificativa obrigatória (RN-13): reprovação, devolução, cancelamentos. */
export function ReasonDialog({
  title,
  description,
  confirmLabel,
  danger = false,
  onConfirm,
  onClose,
}: {
  title: string
  description?: string
  confirmLabel: string
  danger?: boolean
  onConfirm: (reason: string) => Promise<unknown>
  onClose: () => void
}) {
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const tooShort = reason.trim().length < MIN_LENGTH

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (tooShort) return
    setBusy(true)
    setError(null)
    try {
      await onConfirm(reason.trim())
      onClose()
    } catch (caught) {
      setError(caught)
      setBusy(false)
    }
  }

  return (
    <Modal title={title} onClose={onClose} busy={busy}>
      <form onSubmit={submit} className="form">
        {description && <p className="muted">{description}</p>}
        <TextAreaField
          label="Justificativa"
          required
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          hint={`Mínimo de ${MIN_LENGTH} caracteres. Fica registrada no audit trail.`}
          maxLength={1000}
        />
        <InlineError error={error} />
        <div className="form__actions">
          <Button onClick={onClose} disabled={busy}>
            Voltar
          </Button>
          <Button
            type="submit"
            variant={danger ? 'danger' : 'primary'}
            loading={busy}
            disabled={tooShort}
          >
            {confirmLabel}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
