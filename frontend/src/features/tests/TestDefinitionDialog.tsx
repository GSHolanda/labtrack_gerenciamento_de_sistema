import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'

import { ApiError } from '../../api/client'
import { testDefinitionsApi } from '../../api/masterData'
import { Button } from '../../components/Button'
import { CheckboxField, SelectField, TextAreaField, TextField } from '../../components/Field'
import { Modal } from '../../components/Modal'
import { InlineError } from '../../components/States'
import { useToast } from '../../components/toastContext'
import { formatDecimal, parseDecimalInput } from '../../lib/format'
import { INSTRUMENT_TYPE, INSTRUMENT_TYPES } from '../../lib/labels'
import type { InstrumentType, TestDefinition, TestDefinitionInput } from '../../types/api'

function decimalText(value: string | null): string {
  return value === null ? '' : formatDecimal(value)
}

export function TestDefinitionDialog({
  definition,
  onClose,
}: {
  definition?: TestDefinition
  onClose: () => void
}) {
  const editing = definition !== undefined
  const toast = useToast()
  const queryClient = useQueryClient()
  const [code, setCode] = useState(definition?.code ?? '')
  const [name, setName] = useState(definition?.name ?? '')
  const [unit, setUnit] = useState(definition?.unit ?? '')
  const [min, setMin] = useState(decimalText(definition?.spec_min ?? null))
  const [max, setMax] = useState(decimalText(definition?.spec_max ?? null))
  const [method, setMethod] = useState(definition?.method ?? '')
  const [instrumentType, setInstrumentType] = useState<string>(definition?.instrument_type ?? '')
  const [places, setPlaces] = useState(String(definition?.decimal_places ?? 2))
  const [description, setDescription] = useState(definition?.description ?? '')
  const [active, setActive] = useState(definition?.is_active ?? true)
  const [localError, setLocalError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (data: TestDefinitionInput) =>
      editing
        ? testDefinitionsApi.update(definition.id, data)
        : testDefinitionsApi.create(data),
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ['test-definitions'] })
      toast({ title: `Tipo de teste ${saved.code} ${editing ? 'atualizado' : 'criado'}` })
      onClose()
    },
  })
  const fieldErrors = mutation.error instanceof ApiError ? mutation.error.fieldErrors : {}

  function submit(event: FormEvent) {
    event.preventDefault()
    const specMin = min.trim() ? parseDecimalInput(min) : null
    const specMax = max.trim() ? parseDecimalInput(max) : null
    if ((min.trim() && specMin === null) || (max.trim() && specMax === null)) {
      setLocalError('Os limites devem ser números.')
      return
    }
    if (specMin === null && specMax === null) {
      setLocalError('Informe ao menos um limite de especificação.')
      return
    }
    setLocalError(null)
    const data: TestDefinitionInput = {
      name: name.trim(),
      unit: unit.trim(),
      spec_min: specMin,
      spec_max: specMax,
      method: method.trim(),
      instrument_type: (instrumentType || null) as InstrumentType | null,
      decimal_places: Number(places),
      description: description.trim() || null,
    }
    mutation.mutate(editing ? { ...data, is_active: active } : { ...data, code: code.trim() })
  }

  return (
    <Modal
      title={editing ? `Editar ${definition.code}` : 'Novo tipo de teste'}
      onClose={onClose}
      busy={mutation.isPending}
      size="lg"
    >
      <form className="form" onSubmit={submit}>
        {editing && (
          <p className="muted">
            Amostras já atribuídas mantêm os limites copiados no momento da atribuição. O código não
            muda: é a chave usada pelos equipamentos.
          </p>
        )}
        <div className="form__grid">
          <TextField
            label="Código"
            required
            disabled={editing}
            value={code}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
            error={fieldErrors.code}
            hint="Letras, números, - e _ (ex.: PH)."
          />
          <TextField
            label="Nome"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            error={fieldErrors.name}
          />
          <TextField
            label="Unidade"
            required
            value={unit}
            onChange={(event) => setUnit(event.target.value)}
            error={fieldErrors.unit}
          />
          <TextField
            label="Limite mínimo"
            inputMode="decimal"
            value={min}
            onChange={(event) => setMin(event.target.value)}
            error={fieldErrors.spec_min}
          />
          <TextField
            label="Limite máximo"
            inputMode="decimal"
            value={max}
            onChange={(event) => setMax(event.target.value)}
            error={fieldErrors.spec_max}
            hint="Limites inclusivos; deixe um lado vazio para especificação unilateral."
          />
          <TextField
            label="Casas decimais"
            type="number"
            min={0}
            max={6}
            required
            value={places}
            onChange={(event) => setPlaces(event.target.value)}
          />
          <TextField
            label="Método"
            required
            value={method}
            onChange={(event) => setMethod(event.target.value)}
            error={fieldErrors.method}
          />
          <SelectField
            label="Equipamento exigido"
            value={instrumentType}
            onChange={(event) => setInstrumentType(event.target.value)}
            hint="Define quais equipamentos podem enviar o resultado."
          >
            <option value="">Nenhum (somente manual)</option>
            {INSTRUMENT_TYPES.map((type) => (
              <option key={type} value={type}>
                {INSTRUMENT_TYPE[type]}
              </option>
            ))}
          </SelectField>
        </div>
        <TextAreaField
          label="Descrição"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
        {editing && (
          <CheckboxField
            label="Ativo"
            hint="Inativo não pode ser atribuído a novas amostras."
            checked={active}
            onChange={setActive}
          />
        )}
        {localError && <InlineError error={new Error(localError)} />}
        <InlineError error={Object.keys(fieldErrors).length ? null : mutation.error} />
        <div className="form__actions">
          <Button onClick={onClose} disabled={mutation.isPending}>
            Cancelar
          </Button>
          <Button type="submit" variant="primary" loading={mutation.isPending}>
            {editing ? 'Salvar alterações' : 'Criar'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
