import { type FormEvent, useState } from 'react'

import { resultsApi } from '../../api/samples'
import { SpecBadge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { TextAreaField, TextField } from '../../components/Field'
import { Modal } from '../../components/Modal'
import { InlineError } from '../../components/States'
import {
  evaluateSpec,
  formatMeasurement,
  formatSpec,
  parseDecimalInput,
} from '../../lib/format'
import type { ResultRead, SampleTest } from '../../types/api'

const MIN_REASON = 5

/** Lançamento (primeira versão) ou correção (nova versão, com justificativa: RN-17). */
export function ResultDialog({
  sampleTest,
  onSaved,
  onClose,
}: {
  sampleTest: SampleTest
  onSaved: (result: ResultRead) => void
  onClose: () => void
}) {
  const current = sampleTest.current_result
  const amending = current !== null
  const [value, setValue] = useState('')
  const [comment, setComment] = useState('')
  const [reason, setReason] = useState('')
  const [touched, setTouched] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const parsed = parseDecimalInput(value)
  const valueError =
    touched && value.trim() !== '' && parsed === null
      ? 'Informe um número (use vírgula ou ponto para decimais).'
      : undefined
  const preview = parsed ? evaluateSpec(parsed, sampleTest.spec_min, sampleTest.spec_max) : null
  const reasonMissing = amending && reason.trim().length < MIN_REASON
  const spec = formatSpec(
    sampleTest.spec_min,
    sampleTest.spec_max,
    sampleTest.unit,
    sampleTest.decimal_places,
  )

  async function submit(event: FormEvent) {
    event.preventDefault()
    setTouched(true)
    if (!parsed || reasonMissing) return
    setBusy(true)
    setError(null)
    try {
      const result = await resultsApi.enter(sampleTest.id, {
        value: parsed,
        comment: comment.trim() || null,
        change_reason: amending ? reason.trim() : null,
      })
      onSaved(result)
      onClose()
    } catch (caught) {
      setError(caught)
      setBusy(false)
    }
  }

  return (
    <Modal
      title={`${amending ? 'Corrigir' : 'Lançar'} resultado: ${sampleTest.test_name}`}
      onClose={onClose}
      busy={busy}
    >
      <form className="form" onSubmit={submit}>
        <dl className="facts facts--inline">
          <div>
            <dt>Especificação</dt>
            <dd>{spec}</dd>
          </div>
          <div>
            <dt>Método</dt>
            <dd>{sampleTest.method}</dd>
          </div>
          {current && (
            <div>
              <dt>Valor vigente (versão {current.version})</dt>
              <dd>
                {formatMeasurement(current.value, current.unit, sampleTest.decimal_places)}{' '}
                <SpecBadge status={current.spec_status} short />
              </dd>
            </div>
          )}
        </dl>
        <TextField
          label={`Resultado (${sampleTest.unit})`}
          required
          inputMode="decimal"
          autoComplete="off"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onBlur={() => setTouched(true)}
          error={valueError}
          hint={
            preview && (
              <span className="preview">
                Prévia: <SpecBadge status={preview} /> A classificação oficial é feita pelo
                servidor.
              </span>
            )
          }
        />
        {amending && (
          <TextAreaField
            label="Justificativa da correção"
            required
            maxLength={1000}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            error={touched && reasonMissing ? `Mínimo de ${MIN_REASON} caracteres.` : undefined}
            hint="A versão anterior é preservada; a correção fica no audit trail."
          />
        )}
        <TextAreaField
          label="Comentário"
          maxLength={1000}
          value={comment}
          onChange={(event) => setComment(event.target.value)}
        />
        <InlineError error={error} />
        <div className="form__actions">
          <Button onClick={onClose} disabled={busy}>
            Cancelar
          </Button>
          <Button type="submit" variant="primary" loading={busy}>
            {amending ? 'Registrar correção' : 'Registrar resultado'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
