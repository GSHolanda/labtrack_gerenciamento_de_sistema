import { Outlet } from 'react-router'

import { Toaster } from '../components/Toaster'
import { AuthProvider } from '../features/auth/AuthProvider'

/** Provedores que precisam do roteador (autenticação navega; notificações em toda tela). */
export function Root() {
  return (
    <AuthProvider>
      <Toaster>
        <Outlet />
      </Toaster>
    </AuthProvider>
  )
}
