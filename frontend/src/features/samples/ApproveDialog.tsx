import { ShieldCheck } from 'lucide-react'
import { type FormEvent, useState } from 'react'

import { Button } from '../../components/Button'
import { TextAreaField, TextField } from '../../components/Field'
import { Modal } from '../../components/Modal'
import { InlineError } from '../../components/States'

/** RN-12: aprovação com confirmação de senha (assinatura eletrônica simplificada). */
export function ApproveDialog({
  sampleCode,
  onConfirm,
  onClose,
}: {
  sampleCode: string
  onConfirm: (password: string, comment: string | undefined) => Promise<unknown>
  onClose: () => void
}) {
  const [password, setPassword] = useState('')
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onConfirm(password, comment.trim() || undefined)
      onClose()
    } catch (caught) {
      setError(caught)
      setPassword('')
      setBusy(false)
    }
  }

  return (
    <Modal title={`Aprovar ${sampleCode}`} onClose={onClose} busy={busy}>
      <form className="form" onSubmit={submit}>
        <p className="muted">
          A aprovação é registrada em seu nome no audit trail. Confirme sua senha para assinar.
          Não é possível aprovar amostras em que você lançou resultados.
        </p>
        <TextField
          label="Sua senha"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <TextAreaField
          label="Comentário da revisão"
          maxLength={1000}
          value={comment}
          onChange={(event) => setComment(event.target.value)}
        />
        <InlineError error={error} />
        <div className="form__actions">
          <Button onClick={onClose} disabled={busy}>
            Voltar
          </Button>
          <Button
            type="submit"
            variant="success"
            loading={busy}
            disabled={!password}
            icon={<ShieldCheck aria-hidden />}
          >
            Assinar e aprovar
          </Button>
        </div>
      </form>
    </Modal>
  )
}
