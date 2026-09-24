import type { DashboardCharts, DashboardSummary } from '../types/api'
import { http } from './client'

export const dashboardApi = {
  summary: (periodDays: number) =>
    http.get<DashboardSummary>('/dashboard/summary', { period_days: periodDays }),
  charts: (periodDays: number) =>
    http.get<DashboardCharts>('/dashboard/charts', { period_days: periodDays }),
}
