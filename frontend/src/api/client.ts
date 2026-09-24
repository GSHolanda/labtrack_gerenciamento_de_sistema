// Cliente HTTP da API. Toda comunicação com o backend passa por aqui: token,
// serialização, envelope de erro padronizado e sessão expirada.

import type { ErrorEnvelope } from '../types/api'

export const API_BASE = '/api/v1'

type QueryValue = string | number | boolean | null | undefined | Array<string | number>
export type Query = Record<string, QueryValue>

export interface FieldError {
  field: string
  message: string
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown
  readonly requestId: string | null

  constructor(
    status: number,
    code: string,
    message: string,
    details: unknown = null,
    requestId: string | null = null,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
    this.requestId = requestId
  }

  /** Erros de validação por campo ("body.lot_number" → "lot_number"). */
  get fieldErrors(): Record<string, string> {
    if (this.code !== 'VALIDATION_ERROR' || !Array.isArray(this.details)) return {}
    const errors: Record<string, string> = {}
    for (const item of this.details as FieldError[]) {
      const field = item.field.replace(/^(body|query|path)\./, '')
      errors[field] ??= item.message
    }
    return errors
  }
}

interface ApiConfig {
  getToken: () => string | null
  onUnauthorized: () => void
}

const config: ApiConfig = { getToken: () => null, onUnauthorized: () => {} }

/** O provedor de autenticação informa o token e o que fazer quando a sessão expira. */
export function configureApi(options: Partial<ApiConfig>): void {
  Object.assign(config, options)
}

export function buildUrl(path: string, query?: Query): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null || value === '') continue
    if (Array.isArray(value)) value.forEach((item) => params.append(key, String(item)))
    else params.append(key, String(value))
  }
  const search = params.toString()
  return `${API_BASE}${path}${search ? `?${search}` : ''}`
}

interface RequestOptions {
  query?: Query
  body?: unknown
  form?: Record<string, string>
  signal?: AbortSignal
}

async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  const token = config.getToken()
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`

  let body: BodyInit | undefined
  if (options.form) {
    body = new URLSearchParams(options.form)
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
  } else if (options.body !== undefined) {
    body = JSON.stringify(options.body)
    headers['Content-Type'] = 'application/json'
  }

  let response: Response
  try {
    response = await fetch(buildUrl(path, options.query), {
      method,
      headers,
      body,
      signal: options.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'NETWORK_ERROR', 'Não foi possível conectar à API. Tente novamente.')
  }

  if (response.status === 204) return undefined as T
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const error = toApiError(response.status, payload)
    // Só uma requisição autenticada que volta 401 significa sessão expirada/revogada.
    if (response.status === 401 && token) config.onUnauthorized()
    throw error
  }
  return payload as T
}

function toApiError(status: number, payload: unknown): ApiError {
  const envelope = payload as Partial<ErrorEnvelope> | null
  const error = envelope?.error
  if (error && typeof error.code === 'string') {
    return new ApiError(status, error.code, error.message, error.details, error.request_id)
  }
  return new ApiError(status, `HTTP_${status}`, 'Erro inesperado na API.')
}

export const http = {
  get: <T>(path: string, query?: Query, signal?: AbortSignal) =>
    request<T>('GET', path, { query, signal }),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, { body }),
  postForm: <T>(path: string, form: Record<string, string>) =>
    request<T>('POST', path, { form }),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, { body }),
  put: <T>(path: string, body: unknown) => request<T>('PUT', path, { body }),
}

/** Mensagem legível para qualquer erro (ApiError ou inesperado). */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Erro inesperado.'
}
