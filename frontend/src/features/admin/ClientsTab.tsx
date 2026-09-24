import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Plus } from 'lucide-react'
import { type FormEvent, useState } from 'react'

import { ApiError } from '../../api/client'
import { clientsApi } from '../../api/masterData'
import { queryKeys } from '../../api/queryKeys'
import { ActiveBadge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { CheckboxField, TextField } from '../../components/Field'
import { Modal } from '../../components/Modal'
import { Pagination } from '../../components/Pagination'
import { EmptyState, ErrorState, InlineError, LoadingState } from '../../components/States'
import { useToast } from '../../components/toastContext'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import type { Client } from '../../types/api'

export function ClientsTab() {
  const [search, setSearch] = useState('')
  const q = useDebouncedValue(search)
  const [page, setPage] = useState(1)
  const [editing, setEditing] = useState<Client | 'new' | null>(null)
  const filters = { q: q || undefined, page, size: 20, sort: 'name' }
  const query = useQuery({
    queryKey: queryKeys.clients(filters),
    queryFn: () => clientsApi.search(filters),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <div className="toolbar">
        <TextField
          label="Busca"
          type="search"
          placeholder="Código, nome ou CNPJ"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value)
            setPage(1)
          }}
        />
        <Button variant="primary" icon={<Plus aria-hidden />} onClick={() => setEditing('new')}>
          Novo cliente
        </Button>
      </div>
      {query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState error={query.error} />
      ) : query.data.items.length === 0 ? (
        <EmptyState title="Nenhum cliente encontrado" />
      ) : (
        <>
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Código</th>
                  <th>Nome</th>
                  <th>CNPJ</th>
                  <th>Contato</th>
                  <th>Situação</th>
                  <th aria-label="Ações" />
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((client) => (
                  <tr key={client.id} className={client.is_active ? undefined : 'row--muted'}>
                    <td>
                      <code>{client.code}</code>
                    </td>
                    <td>{client.name}</td>
                    <td>{client.tax_id ?? '—'}</td>
                    <td>{client.contact_email ?? '—'}</td>
                    <td>
                      <ActiveBadge active={client.is_active} />
                    </td>
                    <td>
                      <Button
                        size="sm"
                        variant="ghost"
                        icon={<Pencil aria-hidden />}
                        onClick={() => setEditing(client)}
                      >
                        Editar
                      </Button>
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
        <ClientDialog
          client={editing === 'new' ? undefined : editing}
          onClose={() => setEditing(null)}
        />
      )}
    </>
  )
}

function ClientDialog({ client, onClose }: { client?: Client; onClose: () => void }) {
  const editing = client !== undefined
  const toast = useToast()
  const queryClient = useQueryClient()
  const [code, setCode] = useState(client?.code ?? '')
  const [name, setName] = useState(client?.name ?? '')
  const [taxId, setTaxId] = useState(client?.tax_id ?? '')
  const [email, setEmail] = useState(client?.contact_email ?? '')
  const [active, setActive] = useState(client?.is_active ?? true)

  const mutation = useMutation({
    mutationFn: () => {
      const data = {
        name: name.trim(),
        tax_id: taxId.trim() || null,
        contact_email: email.trim() || null,
      }
      return editing
        ? clientsApi.update(client.id, { ...data, is_active: active })
        : clientsApi.create({ ...data, code: code.trim() })
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ['clients'] })
      toast({ title: `Cliente ${saved.code} ${editing ? 'atualizado' : 'criado'}` })
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
      title={editing ? `Editar ${client.code}` : 'Novo cliente'}
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
          label="CNPJ"
          value={taxId}
          onChange={(event) => setTaxId(event.target.value)}
          error={fieldErrors.tax_id}
        />
        <TextField
          label="E-mail de contato"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          error={fieldErrors.contact_email}
        />
        {editing && (
          <CheckboxField
            label="Ativo"
            hint="Cliente inativo não recebe novas amostras."
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
            {editing ? 'Salvar alterações' : 'Criar cliente'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
