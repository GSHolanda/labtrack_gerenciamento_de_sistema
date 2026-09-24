import { useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { authApi } from '../../api/auth'
import { ApiError, configureApi } from '../../api/client'
import { type AuthContextValue, type AuthStatus, AuthContext, permissionChecks } from './authContext'
import { type Session, clearSession, getToken, loadSession, saveSession } from './session'

const EXPIRED_NOTICE = 'Sua sessão expirou. Entre novamente para continuar.'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [session, setSession] = useState<Session | null>(() => loadSession())
  const [status, setStatus] = useState<AuthStatus>(() => (session ? 'loading' : 'anonymous'))
  const [notice, setNotice] = useState<string | null>(null)
  const [endedBy, setEndedBy] = useState<'manual' | 'expired' | null>(null)

  const logout = useCallback(
    (reason?: 'expired') => {
      clearSession()
      setSession(null)
      setStatus('anonymous')
      setNotice(reason === 'expired' ? EXPIRED_NOTICE : null)
      setEndedBy(reason ?? 'manual')
      queryClient.clear()
    },
    [queryClient],
  )

  // Uma requisição autenticada que volta 401 encerra a sessão (token expirado ou revogado).
  useEffect(() => {
    configureApi({ getToken, onUnauthorized: () => logout('expired') })
  }, [logout])

  // Sessão salva: confirma no servidor e atualiza perfil e permissões.
  const validated = useRef(false)
  useEffect(() => {
    if (!session || validated.current) return
    validated.current = true
    authApi
      .me()
      .then((user) => {
        const refreshed = { ...session, user }
        saveSession(refreshed)
        setSession(refreshed)
        setStatus('authenticated')
      })
      .catch((error: unknown) => {
        // 401 já encerrou a sessão; API fora do ar mantém o usuário conhecido.
        if (!(error instanceof ApiError && error.status === 401)) setStatus('authenticated')
      })
  }, [session])

  // Encerra a sessão quando o token expira, mesmo sem nenhuma requisição.
  useEffect(() => {
    if (!session) return
    const remaining = new Date(session.expiresAt).getTime() - Date.now()
    const timer = window.setTimeout(() => logout('expired'), Math.max(remaining, 0))
    return () => window.clearTimeout(timer)
  }, [session, logout])

  const login = useCallback(async (username: string, password: string) => {
    const response = await authApi.login(username, password)
    const next: Session = {
      token: response.access_token,
      expiresAt: response.expires_at,
      user: response.user,
    }
    validated.current = true
    saveSession(next)
    setSession(next)
    setStatus('authenticated')
    setNotice(null)
    setEndedBy(null)
  }, [])

  const value = useMemo<AuthContextValue>(() => {
    const user = status === 'authenticated' ? (session?.user ?? null) : null
    return { status, user, notice, endedBy, login, logout, ...permissionChecks(user) }
  }, [status, session, notice, endedBy, login, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
