import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { Bot, Cpu, ShieldCheck, UserRound, X } from 'lucide-react'
import { Fragment, useState } from 'react'
import { Link } from 'react-router'

import { auditApi } from '../../api/audit'
import { queryKeys } from '../../api/queryKeys'
import { Alert } from '../../components/Alert'
import { Button } from '../../components/Button'
import { SelectField, TextField } from '../../components/Field'
import { PageHeader } from '../../components/PageHeader'
import { Pagination } from '../../components/Pagination'
import { SortableHeader } from '../../components/SortableHeader'
import { EmptyState, ErrorState, InlineError, LoadingState } from '../../components/States'
import { toNumber, useListParams } from '../../hooks/useListParams'
import { dayBoundary, formatDateTime } from '../../lib/format'
import { ACTOR_TYPE, AUDIT_ACTION, AUDIT_ACTIONS, auditActionLabel } from '../../lib/labels'
import type { ActorType, AuditRecord } from '../../types/api'

const ACTOR_ICON = { USER: UserRound, INSTRUMENT: Cpu, SYSTEM: Bot }

const ENTITY_TYPES: Record<string, string> = {
  sample: 'Amostra',
  sample_test: 'Teste da amostra',
  test_result: 'Resultado',
  instrument: 'Equipamento',
  instrument_message: 'Mensagem de equipamento',
  test_definition: 'Tipo de teste',
  product: 'Produto',
  client: 'Cliente',
  user: 'Usuário',
}

export function AuditPage() {
  const list = useListParams()
  const [expanded, setExpanded] = useState<number | null>(null)
  const sampleId = toNumber(list.get('sample_id'))
  const filters = {
    actor_type: (list.get('actor_type') || undefined) as ActorType | undefined,
    action: list.get('action') || undefined,
    entity_type: list.get('entity_type') || undefined,
    sample_id: sampleId,
    occurred_from: list.get('from') ? dayBoundary(list.get('from'), 'start') : undefined,
    occurred_to: list.get('to') ? dayBoundary(list.get('to'), 'end') : undefined,
    page: list.page,
    size: 25,
    sort: list.sort ?? '-occurred_at',
  }
  const query = useQuery({
    queryKey: queryKeys.audit(filters),
    queryFn: () => auditApi.search(filters),
    placeholderData: keepPreviousData,
  })
  const verification = useMutation({ mutationFn: auditApi.verify })
  const hasFilters = [...list.params.keys()].some((key) => key !== 'page' && key !== 'sort')

  return (
    <>
      <PageHeader
        title="Audit Trail"
        subtitle="Registro imutável de quem fez o quê, quando, com valores anteriores e novos."
        actions={
          <Button
            icon={<ShieldCheck aria-hidden />}
            loading={verification.isPending}
            onClick={() => verification.mutate()}
          >
            Verificar integridade
          </Button>
        }
      />
      {verification.data &&
        (verification.data.valid ? (
          <Alert tone="success" title="Cadeia de hashes íntegra">
            {verification.data.checked_records} registros verificados, do primeiro ao último. A
            verificação detecta alteração de conteúdo e quebra de encadeamento.
          </Alert>
        ) : (
          <Alert tone="danger" title="Inconsistência na cadeia de hashes">
            Primeiro registro inválido: #{verification.data.first_invalid_id} (
            {verification.data.error_code}), após {verification.data.checked_records} registros.
          </Alert>
        ))}
      <InlineError error={verification.error} />

      <section className="filters">
        <div className="filters__row">
          <SelectField
            label="Tipo de ator"
            value={list.get('actor_type')}
            onChange={(event) => list.update({ actor_type: event.target.value })}
          >
            <option value="">Todos</option>
            {Object.entries(ACTOR_TYPE).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Ação"
            value={list.get('action')}
            onChange={(event) => list.update({ action: event.target.value })}
          >
            <option value="">Todas</option>
            {AUDIT_ACTIONS.map((action) => (
              <option key={action} value={action}>
                {AUDIT_ACTION[action]}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Entidade"
            value={list.get('entity_type')}
            onChange={(event) => list.update({ entity_type: event.target.value })}
          >
            <option value="">Todas</option>
            {Object.entries(ENTITY_TYPES).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </SelectField>
          <TextField
            label="De"
            type="date"
            value={list.get('from')}
            onChange={(event) => list.update({ from: event.target.value })}
          />
          <TextField
            label="até"
            type="date"
            value={list.get('to')}
            onChange={(event) => list.update({ to: event.target.value })}
          />
        </div>
        {(sampleId || hasFilters) && (
          <div className="filters__row filters__row--chips">
            {sampleId && (
              <span className="chip chip--active">
                Amostra #{sampleId}
                <button
                  type="button"
                  aria-label="Remover filtro de amostra"
                  onClick={() => list.update({ sample_id: null })}
                >
                  <X aria-hidden />
                </button>
              </span>
            )}
            <Button size="sm" variant="ghost" icon={<X aria-hidden />} onClick={list.clear}>
              Limpar filtros
            </Button>
          </div>
        )}
      </section>

      <section className="panel">
        {query.isPending ? (
          <LoadingState />
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        ) : query.data.items.length === 0 ? (
          <EmptyState title="Nenhum registro encontrado" />
        ) : (
          <>
            <div className="table-wrapper">
              <table className="table">
                <thead>
                  <tr>
                    <SortableHeader field="occurred_at" sort={filters.sort} onSort={list.setSort}>
                      Data e hora
                    </SortableHeader>
                    <th>Ator</th>
                    <SortableHeader field="action" sort={filters.sort} onSort={list.setSort}>
                      Ação
                    </SortableHeader>
                    <th>Registro</th>
                    <th>Alteração</th>
                    <th aria-label="Detalhes" />
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((record) => (
                    <AuditRow
                      key={record.id}
                      record={record}
                      expanded={expanded === record.id}
                      onToggle={() => setExpanded(expanded === record.id ? null : record.id)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={query.data.page}
              pages={query.data.pages}
              total={query.data.total}
              size={query.data.size}
              onPage={list.setPage}
            />
          </>
        )}
      </section>
    </>
  )
}

function compact(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value !== 'object') return String(value)
  return Object.entries(value as Record<string, unknown>)
    .map(([key, item]) => `${key}: ${Array.isArray(item) ? item.join(', ') : String(item)}`)
    .join(' · ')
}

function AuditRow({
  record,
  expanded,
  onToggle,
}: {
  record: AuditRecord
  expanded: boolean
  onToggle: () => void
}) {
  const Icon = ACTOR_ICON[record.actor_type]
  const before = compact(record.old_value)
  const after = compact(record.new_value)
  return (
    <Fragment>
      <tr>
        <td className="nowrap">{formatDateTime(record.occurred_at)}</td>
        <td className="nowrap">
          <span className="with-icon" title={ACTOR_TYPE[record.actor_type]}>
            <Icon aria-hidden /> {record.actor_name}
          </span>
        </td>
        <td>{auditActionLabel(record.action)}</td>
        <td>
          <div className="cell-stack">
            <span>{record.entity_label ?? `${record.entity_type} #${record.entity_id}`}</span>
            {record.sample_id && (
              <Link to={`/samples/${record.sample_id}`} className="small-link">
                Abrir amostra
              </Link>
            )}
          </div>
        </td>
        <td className="audit-change">
          {before && <span className="audit-change__old">{before}</span>}
          {after && <span className="audit-change__new">{after}</span>}
          {record.reason && <em>“{record.reason}”</em>}
          {!before && !after && !record.reason && '—'}
        </td>
        <td>
          <Button size="sm" variant="ghost" aria-expanded={expanded} onClick={onToggle}>
            {expanded ? 'Ocultar' : 'Detalhes'}
          </Button>
        </td>
      </tr>
      {expanded && (
        <tr className="row--detail">
          <td colSpan={6}>
            <dl className="facts facts--inline">
              <div>
                <dt>Registro</dt>
                <dd>#{record.id}</dd>
              </div>
              <div>
                <dt>Requisição</dt>
                <dd>{record.request_id ?? '—'}</dd>
              </div>
              <div>
                <dt>IP</dt>
                <dd>{record.ip_address ?? '—'}</dd>
              </div>
              <div className="facts__item--wide">
                <dt>Hash anterior</dt>
                <dd>
                  <code className="hash">{record.previous_hash ?? '— (primeiro registro)'}</code>
                </dd>
              </div>
              <div className="facts__item--wide">
                <dt>Hash do registro</dt>
                <dd>
                  <code className="hash">{record.record_hash}</code>
                </dd>
              </div>
            </dl>
          </td>
        </tr>
      )}
    </Fragment>
  )
}
