import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Cpu, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { instrumentsApi } from '../../api/instruments'
import { queryKeys } from '../../api/queryKeys'
import { InstrumentStatusBadge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { SelectField, TextField } from '../../components/Field'
import { PageHeader } from '../../components/PageHeader'
import { Pagination } from '../../components/Pagination'
import { SortableHeader } from '../../components/SortableHeader'
import { EmptyState, ErrorState, LoadingState } from '../../components/States'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { useListParams } from '../../hooks/useListParams'
import {
  INSTRUMENT_STATUS,
  INSTRUMENT_STATUSES,
  INSTRUMENT_TYPE,
  INSTRUMENT_TYPES,
} from '../../lib/labels'
import type { InstrumentStatus, InstrumentType, InstrumentWithKey } from '../../types/api'
import { useAuth } from '../auth/authContext'
import { ApiKeyDialog } from './ApiKeyDialog'
import { InstrumentDialog } from './InstrumentDialog'
import { CalibrationBadge, ConnectionBadge } from './InstrumentBadges'

export function InstrumentsPage() {
  const { can } = useAuth()
  const list = useListParams()
  const [search, setSearch] = useState(list.get('q'))
  const debounced = useDebouncedValue(search)
  const [creating, setCreating] = useState(false)
  const [issued, setIssued] = useState<InstrumentWithKey | null>(null)

  useEffect(() => {
    if (debounced !== list.get('q')) list.update({ q: debounced })
  }, [debounced, list])

  const filters = {
    q: list.get('q') || undefined,
    status: (list.get('status') || undefined) as InstrumentStatus | undefined,
    instrument_type: (list.get('type') || undefined) as InstrumentType | undefined,
    page: list.page,
    size: 25,
    sort: list.sort,
  }
  const query = useQuery({
    queryKey: queryKeys.instrumentList(filters),
    queryFn: () => instrumentsApi.search(filters),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000, // mantém "online" e "última comunicação" atualizados
  })

  return (
    <>
      <PageHeader
        title="Equipamentos"
        subtitle="Instrumentos integrados via API: status, calibração e última comunicação."
        actions={
          can('INSTRUMENT_MANAGE') && (
            <Button variant="primary" icon={<Plus aria-hidden />} onClick={() => setCreating(true)}>
              Cadastrar equipamento
            </Button>
          )
        }
      />
      <section className="filters">
        <div className="filters__row">
          <TextField
            label="Busca"
            type="search"
            placeholder="Código, nome, local ou série"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <SelectField
            label="Status"
            value={list.get('status')}
            onChange={(event) => list.update({ status: event.target.value })}
          >
            <option value="">Todos</option>
            {INSTRUMENT_STATUSES.map((status) => (
              <option key={status} value={status}>
                {INSTRUMENT_STATUS[status].label}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Tipo"
            value={list.get('type')}
            onChange={(event) => list.update({ type: event.target.value })}
          >
            <option value="">Todos</option>
            {INSTRUMENT_TYPES.map((type) => (
              <option key={type} value={type}>
                {INSTRUMENT_TYPE[type]}
              </option>
            ))}
          </SelectField>
        </div>
      </section>
      <section className="panel">
        {query.isPending ? (
          <LoadingState />
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        ) : query.data.items.length === 0 ? (
          <EmptyState title="Nenhum equipamento encontrado" />
        ) : (
          <>
            <div className="table-wrapper">
              <table className="table">
                <thead>
                  <tr>
                    <SortableHeader field="code" sort={list.sort} onSort={list.setSort}>
                      Equipamento
                    </SortableHeader>
                    <th>Tipo</th>
                    <th>Localização</th>
                    <SortableHeader field="status" sort={list.sort} onSort={list.setSort}>
                      Status
                    </SortableHeader>
                    <SortableHeader
                      field="calibration_due_date"
                      sort={list.sort}
                      onSort={list.setSort}
                    >
                      Calibração
                    </SortableHeader>
                    <SortableHeader
                      field="last_communication_at"
                      sort={list.sort}
                      onSort={list.setSort}
                    >
                      Comunicação
                    </SortableHeader>
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((instrument) => (
                    <tr key={instrument.id}>
                      <td>
                        <div className="cell-stack">
                          <Link to={`/instruments/${instrument.id}`} className="code-link">
                            <Cpu aria-hidden />
                            {instrument.code}
                          </Link>
                          <small>{instrument.name}</small>
                        </div>
                      </td>
                      <td>{INSTRUMENT_TYPE[instrument.instrument_type]}</td>
                      <td>{instrument.location ?? '—'}</td>
                      <td>
                        <InstrumentStatusBadge status={instrument.status} />
                      </td>
                      <td>
                        <CalibrationBadge instrument={instrument} />
                      </td>
                      <td>
                        <ConnectionBadge instrument={instrument} />
                      </td>
                    </tr>
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
      {creating && <InstrumentDialog onClose={() => setCreating(false)} onCreated={setIssued} />}
      {issued && <ApiKeyDialog instrument={issued} rotated={false} onClose={() => setIssued(null)} />}
    </>
  )
}
