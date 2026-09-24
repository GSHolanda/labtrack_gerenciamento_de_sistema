import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Cpu, UserRound, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { queryKeys } from '../../api/queryKeys'
import { type ResultFilters, resultsApi } from '../../api/samples'
import { SpecBadge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { CheckboxField, SelectField, TextField } from '../../components/Field'
import { PageHeader } from '../../components/PageHeader'
import { Pagination } from '../../components/Pagination'
import { SortableHeader } from '../../components/SortableHeader'
import { EmptyState, ErrorState, LoadingState } from '../../components/States'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { useListParams } from '../../hooks/useListParams'
import { useTestDefinitions } from '../../hooks/useReferenceData'
import { dayBoundary, formatDateTime, formatMeasurement, formatSpec } from '../../lib/format'
import type { ResultSource, SpecStatus } from '../../types/api'

const PAGE_SIZE = 25

export function ResultsPage() {
  const list = useListParams()
  const tests = useTestDefinitions()
  const [sampleCode, setSampleCode] = useState(list.get('sample_code'))
  const debouncedCode = useDebouncedValue(sampleCode)

  useEffect(() => {
    if (debouncedCode !== list.get('sample_code')) list.update({ sample_code: debouncedCode })
  }, [debouncedCode, list])

  const history = list.get('history') === '1'
  const filters: ResultFilters = {
    spec_status: (list.get('spec_status') || undefined) as SpecStatus | undefined,
    source: (list.get('source') || undefined) as ResultSource | undefined,
    test_code: list.get('test_code') || undefined,
    sample_code: list.get('sample_code') || undefined,
    entered_from: list.get('from') ? dayBoundary(list.get('from'), 'start') : undefined,
    entered_to: list.get('to') ? dayBoundary(list.get('to'), 'end') : undefined,
    current_only: !history,
    page: list.page,
    size: PAGE_SIZE,
    sort: list.sort,
  }
  const query = useQuery({
    queryKey: queryKeys.resultList(filters),
    queryFn: () => resultsApi.search(filters),
    placeholderData: keepPreviousData,
  })
  const hasFilters = [...list.params.keys()].some((key) => key !== 'page' && key !== 'sort')

  return (
    <>
      <PageHeader
        title="Resultados"
        subtitle="Pesquisa de resultados vigentes e históricos, incluindo os fora da especificação."
      />
      <section className="filters" aria-label="Filtros">
        <div className="filters__row">
          <SelectField
            label="Situação"
            value={list.get('spec_status')}
            onChange={(event) => list.update({ spec_status: event.target.value })}
          >
            <option value="">Todas</option>
            <option value="OOS">OOS</option>
            <option value="IN_SPEC">Conforme</option>
          </SelectField>
          <SelectField
            label="Teste"
            value={list.get('test_code')}
            onChange={(event) => list.update({ test_code: event.target.value })}
          >
            <option value="">Todos</option>
            {tests.data?.map((test) => (
              <option key={test.id} value={test.code}>
                {test.name}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Origem"
            value={list.get('source')}
            onChange={(event) => list.update({ source: event.target.value })}
          >
            <option value="">Todas</option>
            <option value="INSTRUMENT">Equipamento</option>
            <option value="MANUAL">Manual</option>
          </SelectField>
          <TextField
            label="Amostra"
            type="search"
            placeholder="SMP-2026-0001"
            value={sampleCode}
            onChange={(event) => setSampleCode(event.target.value)}
          />
          <TextField
            label="Registrado de"
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
          <CheckboxField
            label="Incluir versões corrigidas"
            hint="Mostra também os valores substituídos por correções."
            checked={history}
            onChange={(checked) => list.update({ history: checked ? '1' : null })}
          />
          {hasFilters && (
            <Button
              size="sm"
              variant="ghost"
              icon={<X aria-hidden />}
              onClick={() => {
                setSampleCode('')
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
          <EmptyState title="Nenhum resultado encontrado" />
        ) : (
          <>
            <div className="table-wrapper">
              <table className="table">
                <thead>
                  <tr>
                    <SortableHeader field="sample_code" sort={list.sort} onSort={list.setSort}>
                      Amostra
                    </SortableHeader>
                    <SortableHeader field="test_code" sort={list.sort} onSort={list.setSort}>
                      Teste
                    </SortableHeader>
                    <SortableHeader field="value" sort={list.sort} onSort={list.setSort}>
                      Resultado
                    </SortableHeader>
                    <th>Especificação</th>
                    <th>Situação</th>
                    <th>Origem</th>
                    <SortableHeader field="entered_at" sort={list.sort} onSort={list.setSort}>
                      Registrado em
                    </SortableHeader>
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((result) => (
                    <tr
                      key={result.id}
                      className={
                        result.spec_status === 'OOS'
                          ? 'row--oos'
                          : !result.is_current
                            ? 'row--muted'
                            : undefined
                      }
                    >
                      <td>
                        <Link to={`/samples/${result.sample_id}`} className="code-link">
                          {result.sample_code}
                        </Link>
                      </td>
                      <td>
                        <div className="cell-stack">
                          <span>{result.test_name}</span>
                          <small>
                            v{result.version}
                            {!result.is_current && ' · substituída'}
                          </small>
                        </div>
                      </td>
                      <td className="nowrap">
                        <strong>
                          {formatMeasurement(result.value, result.unit, result.decimal_places)}
                        </strong>
                      </td>
                      <td className="nowrap">
                        {formatSpec(
                          result.spec_min,
                          result.spec_max,
                          result.unit,
                          result.decimal_places,
                        )}
                      </td>
                      <td>
                        <SpecBadge status={result.spec_status} short />
                      </td>
                      <td>
                        <span className="with-icon">
                          {result.instrument_code ? (
                            <>
                              <Cpu aria-hidden /> {result.instrument_code}
                            </>
                          ) : (
                            <>
                              <UserRound aria-hidden /> {result.entered_by?.full_name}
                            </>
                          )}
                        </span>
                      </td>
                      <td className="nowrap">{formatDateTime(result.entered_at)}</td>
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
    </>
  )
}
