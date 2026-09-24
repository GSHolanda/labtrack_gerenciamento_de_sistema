import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Pencil, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'

import { testDefinitionsApi } from '../../api/masterData'
import { queryKeys } from '../../api/queryKeys'
import { ActiveBadge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { SelectField, TextField } from '../../components/Field'
import { PageHeader } from '../../components/PageHeader'
import { Pagination } from '../../components/Pagination'
import { SortableHeader } from '../../components/SortableHeader'
import { EmptyState, ErrorState, LoadingState } from '../../components/States'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { useListParams } from '../../hooks/useListParams'
import { formatSpec } from '../../lib/format'
import { INSTRUMENT_TYPE } from '../../lib/labels'
import type { TestDefinition } from '../../types/api'
import { useAuth } from '../auth/authContext'
import { TestDefinitionDialog } from './TestDefinitionDialog'

export function TestDefinitionsPage() {
  const { can } = useAuth()
  const list = useListParams()
  const [search, setSearch] = useState(list.get('q'))
  const debounced = useDebouncedValue(search)
  const [editing, setEditing] = useState<TestDefinition | 'new' | null>(null)

  useEffect(() => {
    if (debounced !== list.get('q')) list.update({ q: debounced })
  }, [debounced, list])

  const active = list.get('active')
  const filters = {
    q: list.get('q') || undefined,
    is_active: active === '' ? undefined : active === 'true',
    page: list.page,
    size: 25,
    sort: list.sort,
  }
  const query = useQuery({
    queryKey: queryKeys.testDefinitions(filters),
    queryFn: () => testDefinitionsApi.search(filters),
    placeholderData: keepPreviousData,
  })
  const canManage = can('TEST_DEFINITION_MANAGE')

  return (
    <>
      <PageHeader
        title="Testes"
        subtitle="Catálogo de tipos de teste: unidade, limites padrão, método e equipamento."
        actions={
          canManage && (
            <Button variant="primary" icon={<Plus aria-hidden />} onClick={() => setEditing('new')}>
              Novo tipo de teste
            </Button>
          )
        }
      />
      <section className="filters">
        <div className="filters__row">
          <TextField
            label="Busca"
            type="search"
            placeholder="Código, nome ou método"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <SelectField
            label="Situação"
            value={active}
            onChange={(event) => list.update({ active: event.target.value })}
          >
            <option value="">Todos</option>
            <option value="true">Ativos</option>
            <option value="false">Inativos</option>
          </SelectField>
        </div>
      </section>
      <section className="panel">
        {query.isPending ? (
          <LoadingState />
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        ) : query.data.items.length === 0 ? (
          <EmptyState title="Nenhum tipo de teste encontrado" />
        ) : (
          <>
            <div className="table-wrapper">
              <table className="table">
                <thead>
                  <tr>
                    <SortableHeader field="code" sort={list.sort} onSort={list.setSort}>
                      Código
                    </SortableHeader>
                    <SortableHeader field="name" sort={list.sort} onSort={list.setSort}>
                      Nome
                    </SortableHeader>
                    <th>Especificação padrão</th>
                    <th>Método</th>
                    <th>Equipamento</th>
                    <th>Situação</th>
                    {canManage && <th aria-label="Ações" />}
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((test) => (
                    <tr key={test.id} className={test.is_active ? undefined : 'row--muted'}>
                      <td>
                        <code>{test.code}</code>
                      </td>
                      <td>{test.name}</td>
                      <td className="nowrap">
                        {formatSpec(test.spec_min, test.spec_max, test.unit, test.decimal_places)}
                      </td>
                      <td>{test.method}</td>
                      <td>
                        {test.instrument_type ? (
                          INSTRUMENT_TYPE[test.instrument_type]
                        ) : (
                          <span className="muted">Manual</span>
                        )}
                      </td>
                      <td>
                        <ActiveBadge active={test.is_active} />
                      </td>
                      {canManage && (
                        <td>
                          <Button
                            size="sm"
                            variant="ghost"
                            icon={<Pencil aria-hidden />}
                            onClick={() => setEditing(test)}
                          >
                            Editar
                          </Button>
                        </td>
                      )}
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
      {editing && (
        <TestDefinitionDialog
          definition={editing === 'new' ? undefined : editing}
          onClose={() => setEditing(null)}
        />
      )}
    </>
  )
}
