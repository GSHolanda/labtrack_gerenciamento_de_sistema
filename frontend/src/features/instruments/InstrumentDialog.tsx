import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'

import { ApiError } from '../../api/client'
import { instrumentsApi } from '../../api/instruments'
import { queryKeys } from '../../api/queryKeys'
import { Button } from '../../components/Button'
import { SelectField, TextField } from '../../components/Field'
import { Modal } from '../../components/Modal'
import { InlineError } from '../../components/States'
import { useToast } from '../../components/toastContext'
import { INSTRUMENT_STATUS, INSTRUMENT_STATUSES, INSTRUMENT_TYPE, INSTRUMENT_TYPES } from '../../lib/labels'
import type {
  Instrument,
  InstrumentInput,
  InstrumentStatus,
  InstrumentType,
  InstrumentWithKey,
} from '../../types/api'

export function InstrumentDialog({
  instrument,
  onClose,
  onCreated,
}: {
  instrument?: Instrument
  onClose: () => void
  onCreated?: (created: InstrumentWithKey) => void
}) {
  const editing = instrument !== undefined
  const toast = useToast()
  const queryClient = useQueryClient()
  const [code, setCode] = useState(instrument?.code ?? '')
  const [name, setName] = useState(instrument?.name ?? '')
  const [type, setType] = useState<InstrumentType>(instrument?.instrument_type ?? 'PH_METER')
  const [manufacturer, setManufacturer] = useState(instrument?.manufacturer ?? '')
  const [model, setModel] = useState(instrument?.model ?? '')
  const [serial, setSerial] = useState(instrument?.serial_number ?? '')
  const [location, setLocation] = useState(instrument?.location ?? '')
  const [status, setStatus] = useState<InstrumentStatus>(instrument?.status ?? 'ACTIVE')
  const [calibration, setCalibration] = useState(instrument?.calibration_due_date ?? '')

  const mutation = useMutation({
    mutationFn: (data: InstrumentInput) =>
      editing ? instrumentsApi.update(instrument.id, data) : instrumentsApi.create(data),
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.instruments })
      if (editing) {
        queryClient.setQueryData(queryKeys.instrument(saved.id), saved)
        toast({ title: `Equipamento ${saved.code} atualizado` })
      } else {
        onCreated?.(saved as InstrumentWithKey)
      }
      onClose()
    },
  })
  const fieldErrors = mutation.error instanceof ApiError ? mutation.error.fieldErrors : {}
  const optional = (value: string) => value.trim() || null

  function submit(event: FormEvent) {
    event.preventDefault()
    const common: InstrumentInput = {
      name: name.trim(),
      manufacturer: optional(manufacturer),
      model: optional(model),
      serial_number: optional(serial),
      location: optional(location),
      status,
      calibration_due_date: calibration,
    }
    mutation.mutate(
      editing ? common : { ...common, code: code.trim(), instrument_type: type },
    )
  }

  return (
    <Modal
      title={editing ? `Editar ${instrument.code}` : 'Cadastrar equipamento'}
      onClose={onClose}
      busy={mutation.isPending}
      size="lg"
    >
      <form className="form" onSubmit={submit}>
        <div className="form__grid">
          <TextField
            label="Código"
            required
            disabled={editing}
            value={code}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
            error={fieldErrors.code}
            hint={editing ? 'Não pode ser alterado.' : 'Enviado pelo equipamento (ex.: PH-METER-03).'}
          />
          <TextField
            label="Nome"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            error={fieldErrors.name}
          />
          <SelectField
            label="Tipo"
            disabled={editing}
            value={type}
            onChange={(event) => setType(event.target.value as InstrumentType)}
          >
            {INSTRUMENT_TYPES.map((item) => (
              <option key={item} value={item}>
                {INSTRUMENT_TYPE[item]}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Status"
            value={status}
            onChange={(event) => setStatus(event.target.value as InstrumentStatus)}
          >
            {INSTRUMENT_STATUSES.map((item) => (
              <option key={item} value={item}>
                {INSTRUMENT_STATUS[item].label}
              </option>
            ))}
          </SelectField>
          <TextField
            label="Vencimento da calibração"
            type="date"
            required
            value={calibration}
            onChange={(event) => setCalibration(event.target.value)}
            error={fieldErrors.calibration_due_date}
            hint="Válida até este dia, inclusive."
          />
          <TextField
            label="Localização"
            value={location}
            onChange={(event) => setLocation(event.target.value)}
          />
          <TextField
            label="Fabricante"
            value={manufacturer}
            onChange={(event) => setManufacturer(event.target.value)}
          />
          <TextField label="Modelo" value={model} onChange={(event) => setModel(event.target.value)} />
          <TextField
            label="Número de série"
            value={serial}
            onChange={(event) => setSerial(event.target.value)}
            error={fieldErrors.serial_number}
          />
        </div>
        <InlineError error={Object.keys(fieldErrors).length ? null : mutation.error} />
        <div className="form__actions">
          <Button onClick={onClose} disabled={mutation.isPending}>
            Cancelar
          </Button>
          <Button type="submit" variant="primary" loading={mutation.isPending}>
            {editing ? 'Salvar alterações' : 'Cadastrar e gerar chave'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
