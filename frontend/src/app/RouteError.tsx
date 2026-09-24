import { CircleAlert } from 'lucide-react'
import { isRouteErrorResponse, useRouteError } from 'react-router'

/** Última barreira: erro inesperado de renderização não deixa a tela em branco. */
export function RouteError() {
  const error = useRouteError()
  const message = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : error instanceof Error
      ? error.message
      : 'Erro inesperado.'
  return (
    <div className="status-page">
      <CircleAlert aria-hidden />
      <h1>Algo deu errado</h1>
      <p>{message}</p>
      <a href="/dashboard">Recarregar o LabTrack</a>
    </div>
  )
}
