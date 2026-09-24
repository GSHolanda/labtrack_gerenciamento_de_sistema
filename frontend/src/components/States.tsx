import { CircleAlert, Inbox, LoaderCircle } from 'lucide-react'
import type { ReactNode } from 'react'

import { ApiError, errorMessage } from '../api/client'

export function LoadingState({
  label = 'Carregando…',
  fullPage = false,
}: {
  label?: string
  fullPage?: boolean
}) {
  return (
    <div className={fullPage ? 'state state--full' : 'state'} role="status">
      <LoaderCircle className="spin" aria-hidden />
      <span>{label}</span>
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state state--empty">
      <Inbox aria-hidden />
      <strong>{title}</strong>
      {children && <span>{children}</span>}
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="state state--error" role="alert">
      <CircleAlert aria-hidden />
      <strong>Não foi possível carregar os dados.</strong>
      <span>{errorMessage(error)}</span>
      {error instanceof ApiError && error.requestId && (
        <small>Código da requisição: {error.requestId}</small>
      )}
      {onRetry && (
        <button type="button" className="link-button" onClick={onRetry}>
          Tentar novamente
        </button>
      )}
    </div>
  )
}

/** Erro de uma operação (formulário, ação), exibido junto dela. */
export function InlineError({ error }: { error: unknown }) {
  if (!error) return null
  return (
    <div className="alert alert--danger" role="alert">
      <CircleAlert aria-hidden />
      <div>
        <p>{errorMessage(error)}</p>
        {error instanceof ApiError && <small>{error.code}</small>}
      </div>
    </div>
  )
}
