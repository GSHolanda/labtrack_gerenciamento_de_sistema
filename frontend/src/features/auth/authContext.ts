import { createContext, useContext } from 'react'

import type { CurrentUser, Permission } from '../../types/api'

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous'

export interface AuthContextValue {
  status: AuthStatus
  user: CurrentUser | null
  /** Aviso para a tela de login (ex.: sessão expirada). */
  notice: string | null
  /** Como a última sessão terminou: saída voluntária não guarda a tela de origem. */
  endedBy: 'manual' | 'expired' | null
  login: (username: string, password: string) => Promise<void>
  logout: (reason?: 'expired') => void
  can: (permission: Permission) => boolean
  canAny: (permissions: readonly Permission[]) => boolean
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth precisa estar dentro de <AuthProvider>.')
  return context
}

/** Monta o valor do contexto a partir do usuário (usado pelo provedor e pelos testes). */
export function permissionChecks(user: CurrentUser | null) {
  const granted = new Set(user?.permissions ?? [])
  return {
    can: (permission: Permission) => granted.has(permission),
    canAny: (permissions: readonly Permission[]) =>
      permissions.length === 0 || permissions.some((permission) => granted.has(permission)),
  }
}
