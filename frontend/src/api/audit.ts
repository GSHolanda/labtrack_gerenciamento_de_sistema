import type { ActorType, AuditRecord, AuditVerification, Page } from '../types/api'
import { http } from './client'

export interface AuditFilters {
  actor_type?: ActorType
  action?: string
  entity_type?: string
  entity_id?: string
  sample_id?: number
  instrument_id?: number
  user_id?: number
  occurred_from?: string
  occurred_to?: string
  page?: number
  size?: number
  sort?: string
}

export const auditApi = {
  search: (filters: AuditFilters) => http.get<Page<AuditRecord>>('/audit-logs', { ...filters }),
  verify: () => http.get<AuditVerification>('/audit-logs/verify'),
}
