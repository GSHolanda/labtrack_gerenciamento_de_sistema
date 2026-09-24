// Sessão do usuário no sessionStorage: sobrevive a um recarregamento da página, mas
// termina ao fechar a aba. O token expira no servidor (padrão: 60 minutos).

import type { CurrentUser } from '../../types/api'

const KEY = 'labtrack.session'

// Token em uso, lido pelo cliente HTTP a cada requisição (fora do ciclo de renderização).
let currentToken: string | null = null

export function getToken(): string | null {
  return currentToken
}

export interface Session {
  token: string
  expiresAt: string
  user: CurrentUser
}

export function loadSession(now: Date = new Date()): Session | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return null
    const session = JSON.parse(raw) as Session
    if (!session.token || new Date(session.expiresAt) <= now) {
      sessionStorage.removeItem(KEY)
      return null
    }
    currentToken = session.token
    return session
  } catch {
    return null
  }
}

export function saveSession(session: Session): void {
  currentToken = session.token
  try {
    sessionStorage.setItem(KEY, JSON.stringify(session))
  } catch {
    // Sem armazenamento (modo privado restrito): a sessão vale só enquanto a página estiver aberta.
  }
}

export function clearSession(): void {
  currentToken = null
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    // Nada a limpar.
  }
}
