import { useEffect, useState } from 'react'

type ApiStatus = 'checking' | 'online' | 'offline'

const STATUS_LABEL: Record<ApiStatus, string> = {
  checking: 'verificando…',
  online: 'online',
  offline: 'indisponível',
}

// Tela provisória da ETAPA 1: confirma que frontend e API estão conectados.
// O shell completo (menu lateral, rotas e módulos) é construído na ETAPA 9.
export default function App() {
  const [status, setStatus] = useState<ApiStatus>('checking')

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/v1/health', { signal: controller.signal })
      .then((response) => setStatus(response.ok ? 'online' : 'offline'))
      .catch(() => {
        if (!controller.signal.aborted) setStatus('offline')
      })
    return () => controller.abort()
  }, [])

  return (
    <main className="placeholder">
      <h1>LabTrack</h1>
      <p className="placeholder__subtitle">Laboratory Sample Management System</p>
      <p className={`api-status api-status--${status}`}>API: {STATUS_LABEL[status]}</p>
    </main>
  )
}
