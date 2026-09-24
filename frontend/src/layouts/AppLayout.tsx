import { FlaskConical, LogOut, Menu, X } from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router'

import { useAuth } from '../features/auth/authContext'
import { ROLE } from '../lib/labels'
import { visibleNavigation } from './navigation'

export function AppLayout() {
  const { user, canAny, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)

  if (!user) return null
  const initials = user.full_name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('')

  return (
    <div className="app-shell">
      <aside className={menuOpen ? 'sidebar sidebar--open' : 'sidebar'} aria-label="Menu principal">
        <div className="sidebar__brand">
          <FlaskConical aria-hidden />
          <div>
            <strong>LabTrack</strong>
            <span>Sample Management</span>
          </div>
        </div>
        <nav className="sidebar__nav">
          {visibleNavigation(canAny).map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => (isActive ? 'nav-link nav-link--active' : 'nav-link')}
              onClick={() => setMenuOpen(false)}
            >
              <Icon aria-hidden />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar__footer">
          <div className="user-chip">
            <span className="user-chip__avatar" aria-hidden>
              {initials}
            </span>
            <div>
              <strong>{user.full_name}</strong>
              <span>{ROLE[user.role]}</span>
            </div>
          </div>
          <button type="button" className="nav-link nav-link--button" onClick={() => logout()}>
            <LogOut aria-hidden />
            <span>Sair</span>
          </button>
        </div>
      </aside>
      {menuOpen && (
        <div className="sidebar-backdrop" onClick={() => setMenuOpen(false)} aria-hidden />
      )}
      <div className="app-main">
        <header className="topbar">
          <button
            type="button"
            className="icon-button topbar__menu"
            onClick={() => setMenuOpen((open) => !open)}
            aria-label={menuOpen ? 'Fechar menu' : 'Abrir menu'}
            aria-expanded={menuOpen}
          >
            {menuOpen ? <X aria-hidden /> : <Menu aria-hidden />}
          </button>
          <span className="topbar__brand">LabTrack</span>
          <span className="topbar__user">
            {user.full_name} · {ROLE[user.role]}
          </span>
        </header>
        <main className="content" id="conteudo">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
