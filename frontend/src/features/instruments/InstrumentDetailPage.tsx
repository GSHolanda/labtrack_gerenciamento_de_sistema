import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, KeyRound, Pencil } from 'lucide-react'
import { Fragment, useState } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../../api/client'
import { instrumentsApi } from '../../api/instruments'
import { queryKeys } from '../../api/queryKeys'
import { InstrumentStatusBadge, MessageStatusBadge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { SelectField, TextAreaField } from '../../components/Field'
import { Modal } from '../../components/Modal'
import { PageHeader, Panel } from '../../components/PageHeader'
import { Pagination } from '../../components/Pagination'
import { EmptyState, ErrorState, InlineError, LoadingState } from '../../components/States'
import { NotFound } from '../../components/StatusPages'
import { formatDateTime, formatMeasurement } from '../../lib/format'
import { INSTRUMENT_TYPE } from '../../lib/labels'
import type { Instrument, InstrumentMessageStatus, InstrumentWithKey } from '../../types/api'
import { useAuth } from '../auth/authContext'
import { ApiKeyDialog } from './ApiKeyDialog'
import { CalibrationBadge, ConnectionBadge } from './InstrumentBadges'
import { InstrumentDialog } from './InstrumentDialog'

export function InstrumentDetailPage() {
  const id = Number(useParams().instrumentId)
  const instrument = useQuery({
    queryKey: queryKeys.instrument(id),
    queryFn: () => instrumentsApi.get(id),
    enabled: Number.isInteger(id),
    refetchInterval: 30_000,
  })
  if (!Number.isInteger(id)) return <NotFound />
  if (instrument.isPending) return <LoadingState />
  if (instrument.isError) {
    if (instrument.error instanceof ApiError && instrument.error.status === 404) return <NotFound />
    return <ErrorState error={instrument.error} onRetry={() => instrument.refetch()} />
  }
  return <InstrumentView instrument={instrument.data} />
}

function InstrumentView({ instrument }: { instrument: Instrument }) {
  const { can } = useAuth()
  const [dialog, setDialog] = useState<'edit' | 'rotate' | null>(null)
  const [issued, setIssued] = useState<InstrumentWithKey | null>(null)
  const canManage = can('INSTRUMENT_MANAGE')

  return (
    <>
      <Link to="/instruments" className="back-link">
        <ArrowLeft aria-hidden /> Equipamentos
      </Link>
      <PageHeader
        title={
          <span className="title-with-badges">
            {instrument.code}
            <InstrumentStatusBadge status={instrument.status} />
            <ConnectionBadge instrument={instrument} />
          </span>
        }
        subtitle={`${instrument.name} · ${INSTRUMENT_TYPE[instrument.instrument_type]}`}
        actions={
          canManage && (
            <div className="action-bar">
              <Button icon={<Pencil aria-hidden />} onClick={() => setDialog('edit')}>
                Editar
              </Button>
              <Button icon={<KeyRound aria-hidden />} onClick={() => setDialog('rotate')}>
                Gerar nova chave
              </Button>
            </div>
          )
        }
      />
      <div className="stack">
        <Panel title="Cadastro">
          <dl className="facts">
            <div className="facts__item">
              <dt>Calibração</dt>
              <dd>
                <CalibrationBadge instrument={instrument} />
              </dd>
            </div>
            <div className="facts__item">
              <dt>Última comunicação</dt>
              <dd>{formatDateTime(instrument.last_communication_at)}</dd>
            </div>
            <div className="facts__item">
              <dt>Localização</dt>
              <dd>{instrument.location ?? '—'}</dd>
            </div>
            <div className="facts__item">
              <dt>Fabricante / modelo</dt>
              <dd>
                {[instrument.manufacturer, instrument.model].filter(Boolean).join(' · ') || '—'}
              </dd>
            </div>
            <div className="facts__item">
              <dt>Número de série</dt>
              <dd>{instrument.serial_number ?? '—'}</dd>
            </div>
            <div className="facts__item">
              <dt>Cadastrado em</dt>
              <dd>{formatDateTime(instrument.created_at)}</dd>
            </div>
          </dl>
        </Panel>
        <MessageLog instrumentId={instrument.id} />
      </div>
      {dialog === 'edit' && (
        <InstrumentDialog instrument={instrument} onClose={() => setDialog(null)} />
      )}
      {dialog === 'rotate' && (
        <RotateKeyDialog
          instrument={instrument}
          onClose={() => setDialog(null)}
          onRotated={setIssued}
        />
      )}
      {issued && <ApiKeyDialog instrument={issued} rotated onClose={() => setIssued(null)} />}
    </>
  )
}

function RotateKeyDialog({
  instrument,
  onClose,
  onRotated,
}: {
  instrument: Instrument
  onClose: () => void
  onRotated: (issued: InstrumentWithKey) => void
}) {
  const queryClient = useQueryClient()
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  async function confirm() {
    setBusy(true)
    setError(null)
    try {
      const issued = await instrumentsApi.rotateKey(instrument.id, reason.trim() || null)
      queryClient.invalidateQueries({ queryKey: queryKeys.instruments })
      onRotated(issued)
      onClose()
    } catch (caught) {
      setError(caught)
      setBusy(false)
    }
  }

  return (
    <Modal title={`Gerar nova chave para ${instrument.code}`} onClose={onClose} busy={busy}>
      <div className="form">
        <p className="muted">
          A chave atual deixa de funcionar imediatamente. Atualize a configuração do equipamento
          com a nova chave.
        </p>
        <TextAreaField
          label="Motivo (opcional)"
          value={reason}
          maxLength={1000}
          onChange={(event) => setReason(event.target.value)}
          hint="Se informado, precisa ter pelo menos 5 caracteres. Fica no audit trail."
        />
        <InlineError error={error} />
        <div className="form__actions">
          <Button onClick={onClose} disabled={busy}>
            Cancelar
          </Button>
          <Button
            variant="danger"
            loading={busy}
            disabled={reason.trim().length > 0 && reason.trim().length < 5}
            onClick={confirm}
          >
            Revogar e gerar nova chave
          </Button>
        </div>
      </div>
    </Modal>
  )
}

function MessageLog({ instrumentId }: { instrumentId: number }) {
  const [status, setStatus] = useState<InstrumentMessageStatus | ''>('')
  const [page, setPage] = useState(1)
  const [expanded, setExpanded] = useState<number | null>(null)
  const filters = { status: status || undefined, page, size: 20 }
  const messages = useQuery({
    queryKey: queryKeys.instrumentMessages(instrumentId, filters),
    queryFn: () => instrumentsApi.messages(instrumentId, filters),
    placeholderData: keepPreviousData,
  })

  return (
    <Panel
      title="Log de mensagens"
      actions={
        <SelectField
          label="Situação"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value as InstrumentMessageStatus | '')
            setPage(1)
          }}
        >
          <option value="">Todas</option>
          <option value="ACCEPTED">Aceitas</option>
          <option value="REJECTED">Recusadas</option>
        </SelectField>
      }
    >
      {messages.isPending ? (
        <LoadingState />
      ) : messages.isError ? (
        <ErrorState error={messages.error} />
      ) : messages.data.items.length === 0 ? (
        <EmptyState title="Nenhuma mensagem recebida" />
      ) : (
        <>
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Recebida em</th>
                  <th>Situação</th>
                  <th>Amostra / teste</th>
                  <th>Valor</th>
                  <th>Motivo da recusa</th>
                  <th aria-label="Mensagem" />
                </tr>
              </thead>
              <tbody>
                {messages.data.items.map((message) => (
                  <Fragment key={message.id}>
                    <tr>
                      <td className="nowrap">{formatDateTime(message.received_at)}</td>
                      <td>
                        <MessageStatusBadge status={message.status} />
                      </td>
                      <td>
                        {message.sample_code ?? '—'} / {message.test_code ?? '—'}
                      </td>
                      <td className="nowrap">
                        {message.value !== null
                          ? formatMeasurement(message.value, message.unit ?? '')
                          : '—'}
                      </td>
                      <td>
                        {message.error_code ? (
                          <div className="cell-stack">
                            <code>{message.error_code}</code>
                            <small>{message.error_message}</small>
                          </div>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td>
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-expanded={expanded === message.id}
                          onClick={() => setExpanded(expanded === message.id ? null : message.id)}
                        >
                          {expanded === message.id ? 'Ocultar' : 'Mensagem'}
                        </Button>
                      </td>
                    </tr>
                    {expanded === message.id && (
                      <tr className="row--detail">
                        <td colSpan={6}>
                          <pre className="code-block">
                            {JSON.stringify(message.payload, null, 2)}
                          </pre>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            page={messages.data.page}
            pages={messages.data.pages}
            total={messages.data.total}
            size={messages.data.size}
            onPage={setPage}
          />
        </>
      )}
    </Panel>
  )
}
