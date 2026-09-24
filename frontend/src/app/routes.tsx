import type { ReactNode } from 'react'
import { Navigate, type RouteObject } from 'react-router'

import { NotFound } from '../components/StatusPages'
import { AdminPage } from '../features/admin/AdminPage'
import { AuditPage } from '../features/audit/AuditPage'
import { LoginPage } from '../features/auth/LoginPage'
import { RequireAuth, RequirePermission } from '../features/auth/guards'
import { DashboardPage } from '../features/dashboard/DashboardPage'
import { InstrumentDetailPage } from '../features/instruments/InstrumentDetailPage'
import { InstrumentsPage } from '../features/instruments/InstrumentsPage'
import { ReportsPage } from '../features/reports/ReportsPage'
import { SampleReportPage } from '../features/reports/SampleReportPage'
import { ResultsPage } from '../features/results/ResultsPage'
import { SampleDetailPage } from '../features/samples/SampleDetailPage'
import { SamplesPage } from '../features/samples/SamplesPage'
import { TestDefinitionsPage } from '../features/tests/TestDefinitionsPage'
import { AppLayout } from '../layouts/AppLayout'
import { permissionsFor } from '../layouts/navigation'
import { Root } from './Root'
import { RouteError } from './RouteError'

/** Rota protegida pelas mesmas permissões que exibem o item no menu. */
function guarded(section: string, element: ReactNode): ReactNode {
  return <RequirePermission anyOf={permissionsFor(section)}>{element}</RequirePermission>
}

export const routes: RouteObject[] = [
  {
    element: <Root />,
    errorElement: <RouteError />,
    children: [
      { path: '/login', element: <LoginPage /> },
      {
        path: '/',
        element: (
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        ),
        children: [
          { index: true, element: <Navigate to="/dashboard" replace /> },
          { path: 'dashboard', element: guarded('/dashboard', <DashboardPage />) },
          { path: 'samples', element: guarded('/samples', <SamplesPage />) },
          { path: 'samples/:sampleId', element: guarded('/samples', <SampleDetailPage />) },
          { path: 'tests', element: guarded('/tests', <TestDefinitionsPage />) },
          { path: 'results', element: guarded('/results', <ResultsPage />) },
          { path: 'instruments', element: guarded('/instruments', <InstrumentsPage />) },
          {
            path: 'instruments/:instrumentId',
            element: guarded('/instruments', <InstrumentDetailPage />),
          },
          { path: 'audit', element: guarded('/audit', <AuditPage />) },
          { path: 'reports', element: guarded('/reports', <ReportsPage />) },
          { path: 'reports/:sampleId', element: guarded('/reports', <SampleReportPage />) },
          { path: 'admin', element: guarded('/admin', <AdminPage />) },
          { path: '*', element: <NotFound /> },
        ],
      },
    ],
  },
]
