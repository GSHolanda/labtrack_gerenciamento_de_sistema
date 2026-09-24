import { type FormEvent, useState } from 'react'

import { samplesApi } from '../../api/samples'
import { Button } from '../../components/Button'
import { Modal } from '../../components/Modal'
import { EmptyState, InlineError, LoadingState } from '../../components/States'
import { useTestDefinitions } from '../../hooks/useReferenceData'
import { formatSpec } from '../../lib/format'
import type { SampleDetail } from '../../types/api'

export function AssignTestsDialog({
  sample,
  onSaved,
  onClose,
}: {
  sample: SampleDetail
  onSaved: (sample: SampleDetail) => void
  onClose: () => void
}) {
  const definitions = useTestDefinitions(true)
  const [selected, setSelected] = useState<number[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const assigned = new Set(sample.tests.map((test) => test.test_definition_id))
  const available = definitions.data?.filter((definition) => !assigned.has(definition.id)) ?? []

  const toggle = (id: number) =>
    setSelected((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    )

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onSaved(await samplesApi.assignTests(sample.id, selected))
      onClose()
    } catch (caught) {
      setError(caught)
      setBusy(false)
    }
  }

  return (
    <Modal title={`Atribuir testes a ${sample.sample_code}`} onClose={onClose} busy={busy}>
      <form className="form" onSubmit={submit}>
        <p className="muted">
          Os limites do teste (ou do plano do produto, se houver) são copiados no momento da
          atribuição.
        </p>
        {definitions.isPending ? (
          <LoadingState />
        ) : available.length === 0 ? (
          <EmptyState title="Todos os testes ativos já estão atribuídos" />
        ) : (
          <ul className="check-list">
            {available.map((definition) => (
              <li key={definition.id}>
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={selected.includes(definition.id)}
                    onChange={() => toggle(definition.id)}
                  />
                  <span>
                    {definition.name} <code>{definition.code}</code>
                    <small>
                      {formatSpec(
                        definition.spec_min,
                        definition.spec_max,
                        definition.unit,
                        definition.decimal_places,
                      )}{' '}
                      · {definition.method}
                    </small>
                  </span>
                </label>
              </li>
            ))}
          </ul>
        )}
        <InlineError error={error} />
        <div className="form__actions">
          <Button onClick={onClose} disabled={busy}>
            Cancelar
          </Button>
          <Button type="submit" variant="primary" loading={busy} disabled={!selected.length}>
            Atribuir {selected.length ? `(${selected.length})` : ''}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
