// Formatação para a interface (pt-BR). Valores analíticos chegam como texto decimal
// e são tratados como texto: nenhum dígito registrado é arredondado ou escondido.

import type { Decimal, SpecStatus } from '../types/api'

const LOCALE = 'pt-BR'
const EMPTY = '—'

const dateTimeFormat = new Intl.DateTimeFormat(LOCALE, { dateStyle: 'short', timeStyle: 'short' })
const dateFormat = new Intl.DateTimeFormat(LOCALE, { dateStyle: 'short' })
const longDateFormat = new Intl.DateTimeFormat(LOCALE, {
  weekday: 'long',
  day: '2-digit',
  month: 'long',
  year: 'numeric',
})
const timeFormat = new Intl.DateTimeFormat(LOCALE, { timeStyle: 'short' })
const relativeFormat = new Intl.RelativeTimeFormat(LOCALE, { numeric: 'auto' })

/** Datas da API estão em UTC; sem designador de fuso, são interpretadas como UTC. */
export function parseApiDate(value: string): Date {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value)
  return new Date(hasZone || !value.includes('T') ? value : `${value}Z`)
}

export function formatDateTime(value: string | null | undefined): string {
  return value ? dateTimeFormat.format(parseApiDate(value)) : EMPTY
}

/** Data e hora num fuso específico (ex.: o do laboratório, igual ao PDF do relatório). */
export function formatDateTimeIn(value: string | null | undefined, timeZone: string): string {
  if (!value) return EMPTY
  const format = new Intl.DateTimeFormat(LOCALE, {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone,
  })
  return format.format(parseApiDate(value))
}

export function formatTime(value: string): string {
  return timeFormat.format(parseApiDate(value))
}

export function formatLongDate(value: string): string {
  return longDateFormat.format(parseApiDate(value))
}

/** Data sem hora (ex.: vencimento da calibração): não sofre conversão de fuso. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return EMPTY
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  return dateFormat.format(new Date(year, month - 1, day))
}

export function formatRelative(value: string | null | undefined, now: Date = new Date()): string {
  if (!value) return EMPTY
  const seconds = Math.round((parseApiDate(value).getTime() - now.getTime()) / 1000)
  const steps: [Intl.RelativeTimeFormatUnit, number][] = [
    ['day', 86_400],
    ['hour', 3_600],
    ['minute', 60],
  ]
  for (const [unit, size] of steps) {
    if (Math.abs(seconds) >= size) return relativeFormat.format(Math.round(seconds / size), unit)
  }
  return 'agora'
}

/** Chave "AAAA-MM-DD" do dia local, para agrupar eventos por data. */
export function localDayKey(value: string): string {
  const date = parseApiDate(value)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

// --- Decimais ---------------------------------------------------------------------

const DECIMAL_PATTERN = /^(-?)(\d+)(?:\.(\d+))?$/

/**
 * "7.2100" com 2 casas → "7,21"; "7.2150" com 2 casas → "7,215" (nunca arredonda).
 * Zeros à direita além das casas do teste são removidos; faltantes são completados.
 */
export function formatDecimal(value: Decimal | null | undefined, places?: number): string {
  if (value === null || value === undefined || value === '') return EMPTY
  const match = DECIMAL_PATTERN.exec(String(value).trim())
  if (!match) return String(value)
  const [, sign, integer, fraction = ''] = match
  let digits = fraction.replace(/0+$/, '')
  if (places !== undefined && digits.length < places) digits = digits.padEnd(places, '0')
  const normalizedInteger = integer.replace(/^0+(?=\d)/, '')
  return `${sign}${normalizedInteger}${digits ? `,${digits}` : ''}`
}

export function formatMeasurement(
  value: Decimal | null | undefined,
  unit: string,
  places?: number,
): string {
  const number = formatDecimal(value, places)
  return number === EMPTY ? EMPTY : `${number} ${unit}`
}

/** Faixa de especificação: "5,50 a 7,00 pH", "≤ 0,50 %" ou "≥ 95,0 %". */
export function formatSpec(
  min: Decimal | null,
  max: Decimal | null,
  unit: string,
  places?: number,
): string {
  const low = min === null ? null : formatDecimal(min, places)
  const high = max === null ? null : formatDecimal(max, places)
  if (low !== null && high !== null) return `${low} a ${high} ${unit}`
  if (high !== null) return `≤ ${high} ${unit}`
  if (low !== null) return `≥ ${low} ${unit}`
  return EMPTY
}

/** Aceita "7,21" ou "7.21" e devolve o texto decimal da API ("7.21"); inválido → null. */
export function parseDecimalInput(text: string): Decimal | null {
  const trimmed = text.trim().replace(/\s/g, '')
  if (!/^-?\d+(?:[.,]\d+)?$/.test(trimmed)) return null
  return trimmed.replace(',', '.')
}

/** Quantidade de casas decimais de um texto decimal da API. */
export function decimalPlacesOf(value: Decimal): number {
  return DECIMAL_PATTERN.exec(value)?.[3]?.length ?? 0
}

// Comparação exata: escala os dois números para inteiros (BigInt), sem ponto flutuante.
function toScaled(value: Decimal, scale: number): bigint {
  const match = DECIMAL_PATTERN.exec(value.trim())
  if (!match) throw new Error(`Decimal inválido: ${value}`)
  const [, sign, integer, fraction = ''] = match
  const scaled = BigInt(integer + fraction.padEnd(scale, '0').slice(0, scale))
  return sign ? -scaled : scaled
}

export function compareDecimals(a: Decimal, b: Decimal): number {
  const scale = Math.max(decimalPlacesOf(a), decimalPlacesOf(b))
  const difference = toScaled(a, scale) - toScaled(b, scale)
  return difference === 0n ? 0 : difference < 0n ? -1 : 1
}

/** RN-16 no cliente, só para pré-visualização: o servidor é quem decide. */
export function evaluateSpec(value: Decimal, min: Decimal | null, max: Decimal | null): SpecStatus {
  if (min !== null && compareDecimals(value, min) < 0) return 'OOS'
  if (max !== null && compareDecimals(value, max) > 0) return 'OOS'
  return 'IN_SPEC'
}

// --- Datas em formulários ------------------------------------------------------------

/** Valor para <input type="datetime-local"> a partir de uma data (horário local). */
export function toDateTimeLocalInput(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

/** Converte o valor local de <input type="datetime-local"> para ISO com fuso. */
export function fromDateTimeLocalInput(value: string): string {
  return new Date(value).toISOString()
}

/** Início ou fim do dia local de um <input type="date">, em ISO (UTC). */
export function dayBoundary(value: string, edge: 'start' | 'end'): string {
  const [year, month, day] = value.split('-').map(Number)
  const date =
    edge === 'start'
      ? new Date(year, month - 1, day, 0, 0, 0, 0)
      : new Date(year, month - 1, day, 23, 59, 59, 999)
  return date.toISOString()
}
