import type {
  Instrument,
  InstrumentInput,
  InstrumentMessage,
  InstrumentMessageStatus,
  InstrumentStatus,
  InstrumentType,
  InstrumentWithKey,
  Page,
} from '../types/api'
import { http } from './client'

export interface InstrumentFilters {
  q?: string
  status?: InstrumentStatus
  instrument_type?: InstrumentType
  page?: number
  size?: number
  sort?: string
}

export const instrumentsApi = {
  search: (filters: InstrumentFilters) =>
    http.get<Page<Instrument>>('/instruments', { ...filters }),
  get: (id: number) => http.get<Instrument>(`/instruments/${id}`),
  create: (data: InstrumentInput) => http.post<InstrumentWithKey>('/instruments', data),
  update: (id: number, data: InstrumentInput) =>
    http.patch<Instrument>(`/instruments/${id}`, data),
  rotateKey: (id: number, reason: string | null) =>
    http.post<InstrumentWithKey>(`/instruments/${id}/rotate-key`, reason ? { reason } : undefined),
  messages: (id: number, filters: { status?: InstrumentMessageStatus; page?: number; size?: number }) =>
    http.get<Page<InstrumentMessage>>(`/instruments/${id}/messages`, { ...filters }),
}
