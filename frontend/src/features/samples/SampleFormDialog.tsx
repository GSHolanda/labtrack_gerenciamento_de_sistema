import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'

import { ApiError } from '../../api/client'
import { productsApi } from '../../api/masterData'
import { queryKeys } from '../../api/queryKeys'
import { samplesApi } from '../../api/samples'
import { Button } from '../../components/Button'
import { CheckboxField, SelectField, TextAreaField, TextField } from '../../components/Field'
import { Modal } from '../../components/Modal'
import { InlineError } from '../../components/States'
import { useToast } from '../../components/toastContext'
import { useClients, useProducts } from '../../hooks/useReferenceData'
import {
  formatSpec,
  fromDateTimeLocalInput,
  toDateTimeLocalInput,
} from '../../lib/format'
import { ORIGIN, ORIGINS, PRIORITIES, PRIORITY } from '../../lib/labels'
import type { SampleDetail, SampleOrigin, SamplePriority } from '../../types/api'
import { useAuth } from '../auth/authContext'

interface Props {
  /** Sem amostra: registro. Com amostra: edição dos dados de registro. */
  sample?: SampleDetail
  onClose: () => void
  onSaved: (sample: SampleDetail) => void
}

export function SampleFormDialog({ sample, onClose, onSaved }: Props) {
  const editing = sample !== undefined
  const { user } = useAuth()
  const toast = useToast()
  const queryClient = useQueryClient()
  const products = useProducts(true)
  const clients = useClients(true)

  const [productId, setProductId] = useState('')
  const [clientId, setClientId] = useState('')
  const [lot, setLot] = useState(sample?.lot_number ?? '')
  const [origin, setOrigin] = useState<SampleOrigin>(sample?.origin ?? 'PRODUCTION')
  const [priority, setPriority] = useState<SamplePriority>(sample?.priority ?? 'NORMAL')
  const [receivedAt, setReceivedAt] = useState(() => toDateTimeLocalInput(new Date()))
  const [responsible, setResponsible] = useState(true)
  const [notes, setNotes] = useState(sample?.notes ?? '')

  const plan = useQuery({
    queryKey: queryKeys.specifications(Number(productId)),
    queryFn: () => productsApi.specifications(Number(productId)),
    enabled: !editing && productId !== '',
  })

  const mutation = useMutation({
    mutationFn: () =>
      editing
        ? samplesApi.update(sample.id, {
            version: sample.version,
            lot_number: lot.trim(),
            origin,
            priority,
            notes: notes.trim() || null,
          })
        : samplesApi.create({
            product_id: Number(productId),
            client_id: Number(clientId),
            lot_number: lot.trim(),
            origin,
            priority,
            received_at: fromDateTimeLocalInput(receivedAt),
            responsible_id: responsible && user ? user.id : null,
            notes: notes.trim() || null,
          }),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.sample(saved.id), saved)
      queryClient.invalidateQueries({ queryKey: queryKeys.samples })
      toast({
        title: editing ? 'Dados da amostra atualizados' : `Amostra ${saved.sample_code} registrada`,
        message: editing ? undefined : `${saved.tests.length} teste(s) atribuído(s) pelo plano analítico.`,
      })
      onSaved(saved)
      onClose()
    },
  })

  const fieldErrors = mutation.error instanceof ApiError ? mutation.error.fieldErrors : {}
  const submit = (event: FormEvent) => {
    event.preventDefault()
    mutation.mutate()
  }

  return (
    <Modal
      title={editing ? `Editar ${sample.sample_code}` : 'Registrar amostra'}
      onClose={onClose}
      busy={mutation.isPending}
      size="lg"
    >
      <form className="form" onSubmit={submit}>
        {!editing && (
          <div className="form__grid">
            <SelectField
              label="Produto"
              required
              value={productId}
              onChange={(event) => setProductId(event.target.value)}
              error={fieldErrors.product_id}
            >
              <option value="">Selecione…</option>
              {products.data?.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.name} ({product.code})
                </option>
              ))}
            </SelectField>
            <SelectField
              label="Cliente"
              required
              value={clientId}
              onChange={(event) => setClientId(event.target.value)}
              error={fieldErrors.client_id}
            >
              <option value="">Selecione…</option>
              {clients.data?.map((client) => (
                <option key={client.id} value={client.id}>
                  {client.name}
                </option>
              ))}
            </SelectField>
          </div>
        )}
        <div className="form__grid">
          <TextField
            label="Lote"
            required
            maxLength={50}
            value={lot}
            onChange={(event) => setLot(event.target.value)}
            error={fieldErrors.lot_number}
          />
          <SelectField
            label="Origem"
            value={origin}
            onChange={(event) => setOrigin(event.target.value as SampleOrigin)}
          >
            {ORIGINS.map((item) => (
              <option key={item} value={item}>
                {ORIGIN[item]}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Prioridade"
            value={priority}
            onChange={(event) => setPriority(event.target.value as SamplePriority)}
          >
            {PRIORITIES.map((item) => (
              <option key={item} value={item}>
                {PRIORITY[item].label}
              </option>
            ))}
          </SelectField>
          {!editing && (
            <TextField
              label="Recebida em"
              type="datetime-local"
              required
              value={receivedAt}
              onChange={(event) => setReceivedAt(event.target.value)}
              error={fieldErrors.received_at}
              hint="Não pode estar no futuro."
            />
          )}
        </div>
        {!editing && (
          <CheckboxField
            label="Sou o analista responsável por esta amostra"
            checked={responsible}
            onChange={setResponsible}
          />
        )}
        <TextAreaField
          label="Observações"
          maxLength={2000}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
        />
        {!editing && productId && (
          <div className="plan-preview">
            <strong>Testes atribuídos automaticamente (plano analítico)</strong>
            {plan.data?.length === 0 && (
              <p className="muted">
                O produto não tem plano analítico: atribua os testes depois do registro.
              </p>
            )}
            <ul>
              {plan.data?.map((spec) => (
                <li key={spec.test_definition_id}>
                  <span>{spec.test_name}</span>
                  <small>{formatSpec(spec.spec_min, spec.spec_max, spec.unit)}</small>
                </li>
              ))}
            </ul>
          </div>
        )}
        <InlineError error={Object.keys(fieldErrors).length ? null : mutation.error} />
        <div className="form__actions">
          <Button onClick={onClose} disabled={mutation.isPending}>
            Cancelar
          </Button>
          <Button type="submit" variant="primary" loading={mutation.isPending}>
            {editing ? 'Salvar alterações' : 'Registrar'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
