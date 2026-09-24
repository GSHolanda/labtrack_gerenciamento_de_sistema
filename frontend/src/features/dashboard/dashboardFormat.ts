// Formatação dos indicadores do dashboard e comparação com o período anterior.

import type { Granularity } from '../../types/api'

const NUMBER = new Intl.NumberFormat('pt-BR')
const ONE_DECIMAL = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 })
const MONTHS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']

export function formatCount(value: number): string {
  return NUMBER.format(value)
}

export function formatPercent(rate: number | null): string {
  return rate === null ? '—' : `${ONE_DECIMAL.format(rate * 100)}%`
}

/** Horas legíveis: "5,2 h" abaixo de dois dias; "2 d 4 h" acima. */
export function formatHours(hours: number | null): string {
  if (hours === null) return '—'
  if (hours < 48) return `${ONE_DECIMAL.format(hours)} h`
  const days = Math.floor(hours / 24)
  const rest = Math.round(hours - days * 24)
  return rest ? `${days} d ${rest} h` : `${days} d`
}

/** "YYYY-MM-DD" do intervalo (dia local), sem conversão de fuso. */
function parseBucket(bucket: string): Date {
  const [year, month, day] = bucket.split('-').map(Number)
  return new Date(year, month - 1, day)
}

const pad = (value: number) => String(value).padStart(2, '0')

/** Rótulo curto para o eixo: "24/09" (dia e semana) ou "set/26" (mês). */
export function bucketLabel(bucket: string, granularity: Granularity): string {
  const date = parseBucket(bucket)
  if (granularity === 'month') return `${MONTHS[date.getMonth()]}/${String(date.getFullYear()).slice(2)}`
  return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}`
}

/** Rótulo completo para tooltip e tabela. */
export function bucketTitle(bucket: string, granularity: Granularity): string {
  const date = parseBucket(bucket)
  const day = `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()}`
  if (granularity === 'week') return `Semana de ${day}`
  if (granularity === 'month') return `${MONTHS[date.getMonth()]}/${date.getFullYear()}`
  return day
}

export const GRANULARITY_LABEL: Record<Granularity, string> = {
  day: 'por dia',
  week: 'por semana',
  month: 'por mês',
}

export type DeltaTone = 'good' | 'bad' | 'neutral'

export interface Delta {
  text: string
  direction: 'up' | 'down' | 'flat'
  tone: DeltaTone
}

/**
 * Variação contra o período anterior. `better` diz se subir é bom ('up'),
 * ruim ('down') ou indiferente ('none'). Sem base de comparação, não há variação.
 */
export function delta(
  current: number | null,
  previous: number | null,
  better: 'up' | 'down' | 'none',
  kind: 'count' | 'rate' | 'hours' = 'count',
): Delta | null {
  if (current === null || previous === null) return null
  const difference = current - previous
  const direction = Math.abs(difference) < 1e-9 ? 'flat' : difference > 0 ? 'up' : 'down'
  const tone: DeltaTone =
    direction === 'flat' || better === 'none'
      ? 'neutral'
      : (direction === 'up') === (better === 'up')
        ? 'good'
        : 'bad'
  const sign = difference > 0 ? '+' : difference < 0 ? '−' : ''
  const magnitude = Math.abs(difference)
  const text =
    kind === 'rate'
      ? `${sign}${ONE_DECIMAL.format(magnitude * 100)} p.p.`
      : kind === 'hours'
        ? `${sign}${formatHours(magnitude)}`
        : `${sign}${NUMBER.format(magnitude)}`
  return { text: direction === 'flat' ? 'sem variação' : text, direction, tone }
}
