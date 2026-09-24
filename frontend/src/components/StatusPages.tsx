import { ShieldAlert, SearchX } from 'lucide-react'
import { Link } from 'react-router'

export function Forbidden() {
  return (
    <div className="status-page">
      <ShieldAlert aria-hidden />
      <h1>Acesso negado</h1>
      <p>Seu perfil não tem permissão para acessar esta área.</p>
      <Link to="/dashboard">Voltar ao início</Link>
    </div>
  )
}

export function NotFound() {
  return (
    <div className="status-page">
      <SearchX aria-hidden />
      <h1>Página não encontrada</h1>
      <p>O endereço acessado não existe.</p>
      <Link to="/dashboard">Voltar ao início</Link>
    </div>
  )
}
