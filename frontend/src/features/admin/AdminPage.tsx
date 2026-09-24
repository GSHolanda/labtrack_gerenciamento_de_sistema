import { Building, Package, Users } from 'lucide-react'
import type { ReactNode } from 'react'
import { useSearchParams } from 'react-router'

import { PageHeader } from '../../components/PageHeader'
import type { Permission } from '../../types/api'
import { useAuth } from '../auth/authContext'
import { ClientsTab } from './ClientsTab'
import { ProductsTab } from './ProductsTab'
import { UsersTab } from './UsersTab'

const TABS: { id: string; label: string; icon: ReactNode; permission: Permission }[] = [
  { id: 'users', label: 'Usuários', icon: <Users aria-hidden />, permission: 'USER_MANAGE' },
  { id: 'clients', label: 'Clientes', icon: <Building aria-hidden />, permission: 'MASTER_DATA_MANAGE' },
  { id: 'products', label: 'Produtos', icon: <Package aria-hidden />, permission: 'MASTER_DATA_MANAGE' },
]

export function AdminPage() {
  const { can } = useAuth()
  const [params, setParams] = useSearchParams()
  const tabs = TABS.filter((tab) => can(tab.permission))
  const active = tabs.find((tab) => tab.id === params.get('tab')) ?? tabs[0]

  return (
    <>
      <PageHeader
        title="Administração"
        subtitle="Usuários e perfis, clientes, produtos e plano analítico. Nada é excluído: registros são desativados."
      />
      <div className="tabs" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={tab.id === active?.id}
            className={tab.id === active?.id ? 'tab tab--active' : 'tab'}
            onClick={() => setParams({ tab: tab.id }, { replace: true })}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>
      <section className="panel" role="tabpanel">
        <div className="panel__body">
          {active?.id === 'users' && <UsersTab />}
          {active?.id === 'clients' && <ClientsTab />}
          {active?.id === 'products' && <ProductsTab />}
        </div>
      </section>
    </>
  )
}
