import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Plus, TriangleAlert, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { queryKeys } from '../../api/queryKeys'
import { type SampleFilters, samplesApi } from '../../api/samples'
import { PriorityBadge, SampleStatusBadge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { CheckboxField, SelectField, TextField } from '../../components/Field'
import { PageHeader } from '../../components/PageHeader'
import { Pagination } from '../../components/Pagination'
import { SortableHeader } from '../../components/SortableHeader'
import { EmptyState, ErrorState, LoadingState } from '../../components/States'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { toNumber, useListParams } from '../../hooks/useListParams'
import { useClients, useProducts } from '../../hooks/useReferenceData'
import { dayBoundary, formatDateTime } from '../../lib/format'
import { ORIGIN, PRIORITIES, PRIORITY, SAMPLE_STATUS, SAMPLE_STATUSES } from '../../lib/labels'
import type { SamplePriority, SampleStatus, SampleSummary } from '../../types/api'
import { useAuth } from '../auth/authContext'
import { SampleFormDialog } from './SampleFormDialog'

const PAGE_SIZE = 20

export function SamplesPage() {
  const { user, can } = useAuth()
  const list = useListParams()
  const navigate = useNavigate()
  const [creating, setCreating] = useState(false)
  const [search, setSearch] = useState(list.get('q'))
  const debouncedSearch = useDebouncedValue(search)
  const products = useProducts()
  const clients = useClients()

  useEffect(() => {
    if (debouncedSearch !== list.get('q')) list.update({ q: debouncedSearch })
  }, [debouncedSearch, list])

  const statuses = list.getAll('status') as SampleStatus[]
  const mine = list.get('mine') === '1'
  const filters: SampleFilters = {
    q: list.get('q') || undefined,
    status: statuses.length ? statuses : undefined,
    priority: (list.get('priority') || undefined) as SamplePriority | undefined,
    product_id: toNumber(list.get('product_id')),
    client_id: toNumber(list.get('client_id')),
    responsible_id: mine ? user?.id : undefined,
    received_from: list.get('from') ? dayBoundary(list.get('from'), 'start') : undefined,
    received_to: list.get('to') ? dayBoundary(list.get('to'), 'end') : undefined,
    page: list.page,
    size: PAGE_SIZE,
    sort: list.sort,
  }
  const query = useQuery({
    queryKey: queryKeys.sampleList(filters),
    queryFn: () => samplesApi.search(filters),
    placeholderData: keepPreviousData,
  })

  const toggleStatus = (status: SampleStatus) =>
    list.update({
      status: statuses.includes(status)
        ? statuses.filter((item) => item !== status)
        : [...statuses, status],
    })
  const hasFilters = [...list.params.keys()].some((key) => key !== 'page' && key !== 'sort')

  return (
    <>
      <PageHeader
        title="Amostras"
        subtitle="Registro, acompanhamento do workflow e resultados de cada amostra."
        actions={
          can('SAMPLE_CREATE') && (
            <Button variant="primary" icon={<Plus aria-hidden />} onClick={() => setCreating(true)}>
              Registrar amostra
            </Button>
          )
        }
      />

      <section className="filters" aria-label="Filtros">
        <div className="filters__row">
          <TextField
            label="Busca"
            type="search"
            placeholder="Código, lote, produto ou cliente"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <SelectField
            label="Produto"
            value={list.get('product_id')}
            onChange={(event) => list.update({ product_id: event.target.value })}
          >
            <option value="">Todos</option>
            {products.data?.map((product) => (
              <option key={product.id} value={product.id}>
                {product.name}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Cliente"
            value={list.get('client_id')}
            onChange={(event) => list.update({ client_id: event.target.value })}
          >
            <option value="">Todos</option>
            {clients.data?.map((client) => (
              <option key={client.id} value={client.id}>
                {client.name}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Prioridade"
            value={list.get('priority')}
            onChange={(event) => list.update({ priority: event.target.value })}
          >
            <option value="">Todas</option>
            {PRIORITIES.map((priority) => (
              <option key={priority} value={priority}>
                {PRIORITY[priority].label}
              </option>
            ))}
          </SelectField>
          <TextField
            label="Recebida de"
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
        <div className="filters__row filters__row--chips">
          <div className="chips" role="group" aria-label="Status">
            {SAMPLE_STATUSES.map((status) => (
              <button
                key={status}
                type="button"
                className={statuses.includes(status) ? 'chip chip--active' : 'chip'}
                aria-pressed={statuses.includes(status)}
                onClick={() => toggleStatus(status)}
              >
                {SAMPLE_STATUS[status].label}
              </button>
            ))}
          </div>
          {can('SAMPLE_ANALYZE') && (
            <CheckboxField
              label="Somente sob minha responsabilidade"
              checked={mine}
              onChange={(checked) => list.update({ mine: checked ? '1' : null })}
            />
          )}
          {hasFilters && (
            <Button
              size="sm"
              variant="ghost"
              icon={<X aria-hidden />}
              onClick={() => {
                setSearch('')
                list.clear()
              }}
            >
              Limpar filtros
            </Button>
          )}
        </div>
      </section>

      <section className="panel">
        {query.isPending ? (
          <LoadingState />
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        ) : query.data.items.length === 0 ? (
          <EmptyState title="Nenhuma amostra encontrada">
            {hasFilters ? 'Ajuste ou limpe os filtros.' : 'Registre a primeira amostra.'}
          </EmptyState>
        ) : (
          <>
            <div className="table-wrapper">
              <table className="table table--clickable">
                <thead>
                  <tr>
                    <SortableHeader field="sample_code" sort={list.sort} onSort={list.setSort}>
                      Código
                    </SortableHeader>
                    <th>Produto / cliente</th>
                    <SortableHeader field="lot_number" sort={list.sort} onSort={list.setSort}>
                      Lote
                    </SortableHeader>
                    <SortableHeader field="received_at" sort={list.sort} onSort={list.setSort}>
                      Recebida em
                    </SortableHeader>
                    <SortableHeader field="priority" sort={list.sort} onSort={list.setSort}>
                      Prioridade
                    </SortableHeader>
                    <SortableHeader field="status" sort={list.sort} onSort={list.setSort}>
                      Status
                    </SortableHeader>
                    <th>Testes</th>
                    <th>Responsável</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((sample) => (
                    <SampleRow
                      key={sample.id}
                      sample={sample}
                      onOpen={() => navigate(`/samples/${sample.id}`)}
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

      {creating && (
        <SampleFormDialog
          onClose={() => setCreating(false)}
          onSaved={(sample) => navigate(`/samples/${sample.id}`)}
        />
      )}
    </>
  )
}

function SampleRow({ sample, onOpen }: { sample: SampleSummary; onOpen: () => void }) {
  const percent = sample.tests_total ? (sample.tests_completed / sample.tests_total) * 100 : 0
  return (
    <tr onClick={onOpen}>
      <td className="nowrap">
        <Link
          to={`/samples/${sample.id}`}
          className="code-link"
          onClick={(event) => event.stopPropagation()}
        >
          {sample.sample_code}
        </Link>
        {sample.has_oos && (
          <span className="oos-flag" title="Há resultado vigente fora da especificação">
            <TriangleAlert aria-hidden /> OOS
          </span>
        )}
      </td>
      <td>
        <div className="cell-stack">
          <span>{sample.product.name}</span>
          <small>{sample.client.name}</small>
        </div>
      </td>
      <td>
        <div className="cell-stack nowrap">
          <span>{sample.lot_number}</span>
          <small>{ORIGIN[sample.origin]}</small>
        </div>
      </td>
      <td className="nowrap">{formatDateTime(sample.received_at)}</td>
      <td>
        <PriorityBadge priority={sample.priority} />
      </td>
      <td>
        <SampleStatusBadge status={sample.status} />
      </td>
      <td>
        <div
          className="progress"
          title={`${sample.tests_completed} de ${sample.tests_total} testes concluídos`}
        >
          <div className="progress__bar">
            <span style={{ width: `${percent}%` }} />
          </div>
          <small>
            {sample.tests_completed}/{sample.tests_total}
          </small>
        </div>
      </td>
      <td>{sample.responsible?.full_name ?? '—'}</td>
    </tr>
  )
}
