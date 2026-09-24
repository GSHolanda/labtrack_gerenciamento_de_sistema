import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ListChecks, Pencil, Plus, Trash2 } from 'lucide-react'
import { type FormEvent, useState } from 'react'

import { ApiError } from '../../api/client'
import { productsApi } from '../../api/masterData'
import { queryKeys } from '../../api/queryKeys'
import { ActiveBadge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { CheckboxField, TextAreaField, TextField } from '../../components/Field'
import { Modal } from '../../components/Modal'
import { Pagination } from '../../components/Pagination'
import { EmptyState, ErrorState, InlineError, LoadingState } from '../../components/States'
import { useToast } from '../../components/toastContext'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { useTestDefinitions } from '../../hooks/useReferenceData'
import { formatDecimal, formatSpec, parseDecimalInput } from '../../lib/format'
import type { Product, Specification } from '../../types/api'

export function ProductsTab() {
  const [search, setSearch] = useState('')
  const q = useDebouncedValue(search)
  const [page, setPage] = useState(1)
  const [editing, setEditing] = useState<Product | 'new' | null>(null)
  const [planOf, setPlanOf] = useState<Product | null>(null)
  const filters = { q: q || undefined, page, size: 20, sort: 'name' }
  const query = useQuery({
    queryKey: queryKeys.products(filters),
    queryFn: () => productsApi.search(filters),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <div className="toolbar">
        <TextField
          label="Busca"
          type="search"
          placeholder="Código, nome ou categoria"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value)
            setPage(1)
          }}
        />
        <Button variant="primary" icon={<Plus aria-hidden />} onClick={() => setEditing('new')}>
          Novo produto
        </Button>
      </div>
      {query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState error={query.error} />
      ) : query.data.items.length === 0 ? (
        <EmptyState title="Nenhum produto encontrado" />
      ) : (
        <>
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Código</th>
                  <th>Nome</th>
                  <th>Categoria</th>
                  <th>Situação</th>
                  <th aria-label="Ações" />
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((product) => (
                  <tr key={product.id} className={product.is_active ? undefined : 'row--muted'}>
                    <td>
                      <code>{product.code}</code>
                    </td>
                    <td>{product.name}</td>
                    <td>{product.category ?? '—'}</td>
                    <td>
                      <ActiveBadge active={product.is_active} />
                    </td>
                    <td>
                      <div className="row-actions">
                        <Button
                          size="sm"
                          variant="ghost"
                          icon={<ListChecks aria-hidden />}
                          onClick={() => setPlanOf(product)}
                        >
                          Plano analítico
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          icon={<Pencil aria-hidden />}
                          onClick={() => setEditing(product)}
                        >
                          Editar
                        </Button>
                      </div>
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
            onPage={setPage}
          />
        </>
      )}
      {editing && (
        <ProductDialog
          product={editing === 'new' ? undefined : editing}
          onClose={() => setEditing(null)}
        />
      )}
      {planOf && <PlanDialog product={planOf} onClose={() => setPlanOf(null)} />}
    </>
  )
}

function ProductDialog({ product, onClose }: { product?: Product; onClose: () => void }) {
  const editing = product !== undefined
  const toast = useToast()
  const queryClient = useQueryClient()
  const [code, setCode] = useState(product?.code ?? '')
  const [name, setName] = useState(product?.name ?? '')
  const [category, setCategory] = useState(product?.category ?? '')
  const [description, setDescription] = useState(product?.description ?? '')
  const [active, setActive] = useState(product?.is_active ?? true)

  const mutation = useMutation({
    mutationFn: () => {
      const data = {
        name: name.trim(),
        category: category.trim() || null,
        description: description.trim() || null,
      }
      return editing
        ? productsApi.update(product.id, { ...data, is_active: active })
        : productsApi.create({ ...data, code: code.trim() })
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ['products'] })
      toast({ title: `Produto ${saved.code} ${editing ? 'atualizado' : 'criado'}` })
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
      title={editing ? `Editar ${product.code}` : 'Novo produto'}
      onClose={onClose}
      busy={mutation.isPending}
    >
      <form className="form" onSubmit={submit}>
        <TextField
          label="Código"
          required
          disabled={editing}
          value={code}
          onChange={(event) => setCode(event.target.value.toUpperCase())}
          error={fieldErrors.code}
        />
        <TextField
          label="Nome"
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
          error={fieldErrors.name}
        />
        <TextField
          label="Categoria"
          value={category}
          onChange={(event) => setCategory(event.target.value)}
        />
        <TextAreaField
          label="Descrição"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
        {editing && (
          <CheckboxField
            label="Ativo"
            hint="Produto inativo não recebe novas amostras."
            checked={active}
            onChange={setActive}
          />
        )}
        <InlineError error={Object.keys(fieldErrors).length ? null : mutation.error} />
        <div className="form__actions">
          <Button onClick={onClose} disabled={mutation.isPending}>
            Cancelar
          </Button>
          <Button type="submit" variant="primary" loading={mutation.isPending}>
            {editing ? 'Salvar alterações' : 'Criar produto'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

interface PlanRow {
  testDefinitionId: number
  min: string
  max: string
}

function toRows(specs: Specification[]): PlanRow[] {
  // Só os limites próprios do produto; em branco, vale o padrão do tipo de teste.
  return specs.map((spec) => ({
    testDefinitionId: spec.test_definition_id,
    min: spec.product_spec_min === null ? '' : formatDecimal(spec.product_spec_min),
    max: spec.product_spec_max === null ? '' : formatDecimal(spec.product_spec_max),
  }))
}

/** Plano analítico: testes atribuídos automaticamente e limites próprios do produto. */
function PlanDialog({ product, onClose }: { product: Product; onClose: () => void }) {
  const plan = useQuery({
    queryKey: queryKeys.specifications(product.id),
    queryFn: () => productsApi.specifications(product.id),
  })
  return (
    <Modal title={`Plano analítico: ${product.name}`} onClose={onClose} size="lg">
      {plan.isPending ? (
        <LoadingState />
      ) : plan.isError ? (
        <ErrorState error={plan.error} />
      ) : (
        <PlanEditor product={product} initial={toRows(plan.data)} onClose={onClose} />
      )}
    </Modal>
  )
}

function PlanEditor({
  product,
  initial,
  onClose,
}: {
  product: Product
  initial: PlanRow[]
  onClose: () => void
}) {
  const toast = useToast()
  const queryClient = useQueryClient()
  const definitions = useTestDefinitions(true)
  const [rows, setRows] = useState<PlanRow[]>(initial)
  const [adding, setAdding] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)

  const byId = new Map(definitions.data?.map((definition) => [definition.id, definition]))
  const used = new Set(rows.map((row) => row.testDefinitionId))
  const available = definitions.data?.filter((definition) => !used.has(definition.id)) ?? []

  const mutation = useMutation({
    mutationFn: (items: { test_definition_id: number; spec_min: string | null; spec_max: string | null }[]) =>
      productsApi.replaceSpecifications(product.id, items),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.specifications(product.id), saved)
      toast({
        title: 'Plano analítico salvo',
        message: 'Vale para as próximas amostras; as já registradas não mudam.',
      })
      onClose()
    },
  })

  const update = (index: number, change: Partial<PlanRow>) =>
    setRows((current) => current.map((row, i) => (i === index ? { ...row, ...change } : row)))

  function submit(event: FormEvent) {
    event.preventDefault()
    const items = []
    for (const row of rows) {
      const min = row.min.trim() ? parseDecimalInput(row.min) : null
      const max = row.max.trim() ? parseDecimalInput(row.max) : null
      if ((row.min.trim() && min === null) || (row.max.trim() && max === null)) {
        setLocalError('Os limites devem ser números.')
        return
      }
      items.push({ test_definition_id: row.testDefinitionId, spec_min: min, spec_max: max })
    }
    setLocalError(null)
    mutation.mutate(items)
  }

  return (
    <form className="form" onSubmit={submit}>
      <p className="muted">
        Os testes do plano são atribuídos automaticamente no registro da amostra. Limites em branco
        usam o padrão do tipo de teste; um limite do produto prevalece sobre o padrão.
      </p>
      {rows.length === 0 ? (
        <EmptyState title="Nenhum teste no plano" />
      ) : (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Teste</th>
                <th>Padrão</th>
                <th>Mínimo do produto</th>
                <th>Máximo do produto</th>
                <th aria-label="Remover" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => {
                const definition = byId.get(row.testDefinitionId)
                return (
                  <tr key={row.testDefinitionId}>
                    <td>{definition ? `${definition.name} (${definition.code})` : row.testDefinitionId}</td>
                    <td className="nowrap">
                      {definition &&
                        formatSpec(
                          definition.spec_min,
                          definition.spec_max,
                          definition.unit,
                          definition.decimal_places,
                        )}
                    </td>
                    <td>
                      <input
                        className="input input--compact"
                        inputMode="decimal"
                        aria-label={`Mínimo para ${definition?.name ?? 'teste'}`}
                        value={row.min}
                        onChange={(event) => update(index, { min: event.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        className="input input--compact"
                        inputMode="decimal"
                        aria-label={`Máximo para ${definition?.name ?? 'teste'}`}
                        value={row.max}
                        onChange={(event) => update(index, { max: event.target.value })}
                      />
                    </td>
                    <td>
                      <button
                        type="button"
                        className="icon-button"
                        aria-label={`Remover ${definition?.name ?? 'teste'}`}
                        onClick={() => setRows(rows.filter((_, i) => i !== index))}
                      >
                        <Trash2 aria-hidden />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      {available.length > 0 && (
        <div className="toolbar">
          <select
            className="input"
            aria-label="Teste a adicionar"
            value={adding}
            onChange={(event) => setAdding(event.target.value)}
          >
            <option value="">Adicionar teste…</option>
            {available.map((definition) => (
              <option key={definition.id} value={definition.id}>
                {definition.name} ({definition.code})
              </option>
            ))}
          </select>
          <Button
            icon={<Plus aria-hidden />}
            disabled={!adding}
            onClick={() => {
              setRows([...rows, { testDefinitionId: Number(adding), min: '', max: '' }])
              setAdding('')
            }}
          >
            Adicionar
          </Button>
        </div>
      )}
      {localError && <InlineError error={new Error(localError)} />}
      <InlineError error={mutation.error} />
      <div className="form__actions">
        <Button onClick={onClose} disabled={mutation.isPending}>
          Cancelar
        </Button>
        <Button type="submit" variant="primary" loading={mutation.isPending}>
          Salvar plano
        </Button>
      </div>
    </form>
  )
}
