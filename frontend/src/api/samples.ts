import type {
  Page,
  ResultEntry,
  ResultListItem,
  ResultRead,
  SampleAction,
  SampleCreate,
  SampleDetail,
  SamplePriority,
  SampleStatus,
  SampleSummary,
  SampleUpdate,
  SpecStatus,
  ResultSource,
  TimelineEvent,
} from '../types/api'
import { http } from './client'

export interface SampleFilters {
  q?: string
  status?: SampleStatus[]
  priority?: SamplePriority
  product_id?: number
  client_id?: number
  responsible_id?: number
  received_from?: string
  received_to?: string
  page?: number
  size?: number
  sort?: string
}

export interface ResultFilters {
  spec_status?: SpecStatus
  source?: ResultSource
  test_code?: string
  sample_code?: string
  entered_from?: string
  entered_to?: string
  current_only?: boolean
  page?: number
  size?: number
  sort?: string
}

// Cada ação do workflow é uma rota própria (docs/api.md).
const ACTION_PATH: Record<SampleAction, string> = {
  start_analysis: 'start-analysis',
  submit_for_review: 'submit-for-review',
  approve: 'approve',
  reject: 'reject',
  return_to_analysis: 'return-to-analysis',
  cancel: 'cancel',
}

export type ActionPayload = { reason: string } | { password: string; comment?: string } | undefined

export const samplesApi = {
  search: (filters: SampleFilters) =>
    http.get<Page<SampleSummary>>('/samples', { ...filters }),
  get: (id: number) => http.get<SampleDetail>(`/samples/${id}`),
  create: (data: SampleCreate) => http.post<SampleDetail>('/samples', data),
  update: (id: number, data: SampleUpdate) => http.patch<SampleDetail>(`/samples/${id}`, data),
  assignTests: (id: number, testDefinitionIds: number[]) =>
    http.post<SampleDetail>(`/samples/${id}/tests`, { test_definition_ids: testDefinitionIds }),
  cancelTest: (sampleTestId: number, reason: string) =>
    http.post<SampleDetail>(`/sample-tests/${sampleTestId}/cancel`, { reason }),
  act: (id: number, action: SampleAction, payload?: ActionPayload) =>
    http.post<SampleDetail>(`/samples/${id}/${ACTION_PATH[action]}`, payload),
  timeline: (id: number, page = 1, size = 100) =>
    http.get<Page<TimelineEvent>>(`/samples/${id}/timeline`, { page, size }),
}

export const resultsApi = {
  enter: (sampleTestId: number, data: ResultEntry) =>
    http.post<ResultRead>(`/sample-tests/${sampleTestId}/results`, data),
  history: (sampleTestId: number) =>
    http.get<ResultRead[]>(`/sample-tests/${sampleTestId}/results`),
  search: (filters: ResultFilters) => http.get<Page<ResultListItem>>('/results', { ...filters }),
}
