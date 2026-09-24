import {
  ClipboardList,
  Cpu,
  FileText,
  FlaskConical,
  LayoutDashboard,
  type LucideIcon,
  Settings,
  ShieldCheck,
  TestTubes,
} from 'lucide-react'

import type { Permission } from '../types/api'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  /** Permissões que dão acesso (qualquer uma). Vazio: todo usuário autenticado. */
  anyOf: readonly Permission[]
}

// Fonte única do menu e da proteção das rotas: o mesmo item define os dois.
export const NAVIGATION: readonly NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, anyOf: ['DASHBOARD_VIEW'] },
  { to: '/samples', label: 'Amostras', icon: FlaskConical, anyOf: ['SAMPLE_READ'] },
  { to: '/tests', label: 'Testes', icon: TestTubes, anyOf: [] },
  { to: '/results', label: 'Resultados', icon: ClipboardList, anyOf: ['SAMPLE_READ'] },
  { to: '/instruments', label: 'Equipamentos', icon: Cpu, anyOf: [] },
  { to: '/audit', label: 'Audit Trail', icon: ShieldCheck, anyOf: ['AUDIT_READ'] },
  { to: '/reports', label: 'Relatórios', icon: FileText, anyOf: ['REPORT_EXPORT'] },
  {
    to: '/admin',
    label: 'Administração',
    icon: Settings,
    anyOf: ['USER_MANAGE', 'MASTER_DATA_MANAGE'],
  },
]

export function permissionsFor(path: string): readonly Permission[] {
  return NAVIGATION.find((item) => item.to === path)?.anyOf ?? []
}

export function visibleNavigation(canAny: (permissions: readonly Permission[]) => boolean) {
  return NAVIGATION.filter((item) => canAny(item.anyOf))
}
