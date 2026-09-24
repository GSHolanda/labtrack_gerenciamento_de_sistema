import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Plus } from 'lucide-react'
import { type FormEvent, useState } from 'react'

import { ApiError } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import { usersApi } from '../../api/users'
import { ActiveBadge, Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { CheckboxField, SelectField, TextField } from '../../components/Field'
import { Modal } from '../../components/Modal'
import { Pagination } from '../../components/Pagination'
import { EmptyState, ErrorState, InlineError, LoadingState } from '../../components/States'
import { useToast } from '../../components/toastContext'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { formatDateTime } from '../../lib/format'
import { ROLE, ROLES } from '../../lib/labels'
import type { RoleCode, User } from '../../types/api'
import { useAuth } from '../auth/authContext'

export function UsersTab() {
  const [search, setSearch] = useState('')
  const q = useDebouncedValue(search)
  const [role, setRole] = useState('')
  const [page, setPage] = useState(1)
  const [editing, setEditing] = useState<User | 'new' | null>(null)
  const filters = { q: q || undefined, role: (role || undefined) as RoleCode | undefined, page, size: 20 }
  const query = useQuery({
    queryKey: queryKeys.users(filters),
    queryFn: () => usersApi.search(filters),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <div className="toolbar">
        <TextField
          label="Busca"
          type="search"
          placeholder="Nome, login ou e-mail"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value)
            setPage(1)
          }}
        />
        <SelectField
          label="Perfil"
          value={role}
          onChange={(event) => {
            setRole(event.target.value)
            setPage(1)
          }}
        >
          <option value="">Todos</option>
          {ROLES.map((item) => (
            <option key={item} value={item}>
              {ROLE[item]}
            </option>
          ))}
        </SelectField>
        <Button variant="primary" icon={<Plus aria-hidden />} onClick={() => setEditing('new')}>
          Novo usuário
        </Button>
      </div>
      {query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState error={query.error} />
      ) : query.data.items.length === 0 ? (
        <EmptyState title="Nenhum usuário encontrado" />
      ) : (
        <>
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Login</th>
                  <th>Perfil</th>
                  <th>Situação</th>
                  <th>Último acesso</th>
                  <th aria-label="Ações" />
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((user) => (
                  <tr key={user.id} className={user.is_active ? undefined : 'row--muted'}>
                    <td>
                      <div className="cell-stack">
                        <span>{user.full_name}</span>
                        <small>{user.email}</small>
                      </div>
                    </td>
                    <td>
                      <code>{user.username}</code>
                    </td>
                    <td>
                      <Badge tone="info">{ROLE[user.role]}</Badge>
                    </td>
                    <td>
                      <ActiveBadge active={user.is_active} />
                    </td>
                    <td className="nowrap">{formatDateTime(user.last_login_at)}</td>
                    <td>
                      <Button
                        size="sm"
                        variant="ghost"
                        icon={<Pencil aria-hidden />}
                        onClick={() => setEditing(user)}
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
        <UserDialog user={editing === 'new' ? undefined : editing} onClose={() => setEditing(null)} />
      )}
    </>
  )
}

function UserDialog({ user, onClose }: { user?: User; onClose: () => void }) {
  const editing = user !== undefined
  const { user: current } = useAuth()
  const toast = useToast()
  const queryClient = useQueryClient()
  const [username, setUsername] = useState(user?.username ?? '')
  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [email, setEmail] = useState(user?.email ?? '')
  const [role, setRole] = useState<RoleCode>(user?.role ?? 'ANALYST')
  const [password, setPassword] = useState('')
  const [active, setActive] = useState(user?.is_active ?? true)
  const self = editing && current?.id === user.id

  const mutation = useMutation({
    mutationFn: () =>
      editing
        ? usersApi.update(user.id, {
            full_name: fullName.trim(),
            email: email.trim(),
            role,
            is_active: active,
            ...(password ? { password } : {}),
          })
        : usersApi.create({
            username: username.trim(),
            full_name: fullName.trim(),
            email: email.trim(),
            role,
            password,
          }),
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      toast({ title: `Usuário ${saved.username} ${editing ? 'atualizado' : 'criado'}` })
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
      title={editing ? `Editar ${user.username}` : 'Novo usuário'}
      onClose={onClose}
      busy={mutation.isPending}
    >
      <form className="form" onSubmit={submit}>
        <TextField
          label="Login"
          required
          disabled={editing}
          value={username}
          onChange={(event) => setUsername(event.target.value.toLowerCase())}
          error={fieldErrors.username}
          hint="Letras minúsculas, números, ponto, hífen ou sublinhado."
        />
        <TextField
          label="Nome completo"
          required
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
          error={fieldErrors.full_name}
        />
        <TextField
          label="E-mail"
          type="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          error={fieldErrors.email}
        />
        <SelectField
          label="Perfil"
          value={role}
          disabled={self}
          onChange={(event) => setRole(event.target.value as RoleCode)}
          hint={self ? 'Você não pode alterar o próprio perfil.' : undefined}
        >
          {ROLES.map((item) => (
            <option key={item} value={item}>
              {ROLE[item]}
            </option>
          ))}
        </SelectField>
        <TextField
          label={editing ? 'Nova senha' : 'Senha'}
          type="password"
          autoComplete="new-password"
          required={!editing}
          minLength={8}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={fieldErrors.password}
          hint={editing ? 'Deixe em branco para manter a senha atual.' : 'Mínimo de 8 caracteres.'}
        />
        {editing && !self && (
          <CheckboxField
            label="Ativo"
            hint="Usuários não são excluídos: desative para bloquear o acesso."
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
            {editing ? 'Salvar alterações' : 'Criar usuário'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
