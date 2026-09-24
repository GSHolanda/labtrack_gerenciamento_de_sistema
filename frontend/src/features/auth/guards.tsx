import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'

import { LoadingState } from '../../components/States'
import { Forbidden } from '../../components/StatusPages'
import type { Permission } from '../../types/api'
import { useAuth } from './authContext'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status, endedBy } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <LoadingState label="Verificando a sessão…" fullPage />
  if (status === 'anonymous') {
    // Sessão expirada ou link direto: volta à tela pedida depois do login.
    // Saída voluntária: o próximo usuário começa do início.
    const state = endedBy === 'manual' ? undefined : { from: location }
    return <Navigate to="/login" replace state={state} />
  }
  return children
}

/** A interface esconde o que o perfil não pode fazer; a autorização real é do backend. */
export function RequirePermission({
  anyOf,
  children,
}: {
  anyOf: readonly Permission[]
  children: ReactNode
}) {
  const { canAny } = useAuth()
  return canAny(anyOf) ? children : <Forbidden />
}

export function Can({ permission, children }: { permission: Permission; children: ReactNode }) {
  const { can } = useAuth()
  return can(permission) ? children : null
}
