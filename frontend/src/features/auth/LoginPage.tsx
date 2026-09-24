import { FlaskConical, LogIn } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Navigate, useLocation } from 'react-router'

import { ApiError } from '../../api/client'
import { Alert } from '../../components/Alert'
import { Button } from '../../components/Button'
import { TextField } from '../../components/Field'
import { useAuth } from './authContext'

const DEMO_USERS = [
  ['carlos.silva', 'Analista'],
  ['ana.souza', 'Revisora'],
  ['marcos.lima', 'Gestor'],
  ['admin', 'Administrador'],
] as const

const SHOW_DEMO_HINT = import.meta.env.DEV || import.meta.env.VITE_DEMO_MODE === 'true'

export function LoginPage() {
  const { status, login, notice } = useAuth()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (status === 'authenticated') {
    const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname
    return <Navigate to={from && from !== '/login' ? from : '/dashboard'} replace />
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(username.trim(), password)
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : 'Não foi possível entrar. Verifique a conexão com a API.',
      )
      setBusy(false)
    }
  }

  return (
    <div className="login">
      <section className="login__brand" aria-hidden>
        <FlaskConical />
        <h1>LabTrack</h1>
        <p>Gestão de amostras laboratoriais com rastreabilidade completa.</p>
        <ul>
          <li>Workflow controlado do recebimento à aprovação</li>
          <li>Avaliação automática de especificação (OOS)</li>
          <li>Audit trail imutável e integração com equipamentos</li>
        </ul>
      </section>
      <section className="login__panel">
        <form className="login__form form" onSubmit={submit}>
          <div>
            <h2>Entrar</h2>
            <p className="muted">Use seu usuário e senha do laboratório.</p>
          </div>
          {notice && <Alert tone="warning" title={notice} />}
          {error && <Alert tone="danger" title={error} />}
          <TextField
            label="Usuário"
            name="username"
            autoComplete="username"
            required
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
          <TextField
            label="Senha"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <Button type="submit" variant="primary" loading={busy} icon={<LogIn aria-hidden />}>
            Entrar
          </Button>
          {SHOW_DEMO_HINT && (
            <div className="login__hint">
              <strong>Dados de demonstração</strong>
              <span>
                Senha <code>Demo@2026</code> para:{' '}
                {DEMO_USERS.map(([name, role], index) => (
                  <span key={name}>
                    {index > 0 && ', '}
                    <button type="button" className="link-button" onClick={() => setUsername(name)}>
                      {name}
                    </button>{' '}
                    ({role})
                  </span>
                ))}
              </span>
            </div>
          )}
        </form>
      </section>
    </div>
  )
}
