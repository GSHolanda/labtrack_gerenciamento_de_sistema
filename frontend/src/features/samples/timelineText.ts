// Texto legível de cada evento da Sample Timeline, a partir do audit trail.

import { formatDecimal } from '../../lib/format'
import { ORIGIN, PRIORITY, auditActionLabel, sampleStatusLabel } from '../../lib/labels'
import type { SampleOrigin, SamplePriority, TimelineEvent } from '../../types/api'

export type EventTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info'

export interface EventDescription {
  title: string
  details: string[]
  tone: EventTone
}

type Values = Record<string, unknown>

const FIELD_LABEL: Record<string, string> = {
  lot_number: 'lote',
  origin: 'origem',
  priority: 'prioridade',
  responsible_id: 'responsável',
  notes: 'observações',
}

function values(value: unknown): Values {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Values) : {}
}

function text(value: unknown): string {
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

/** "SMP-2026-0001 / PH" → "PH". */
function testOf(event: TimelineEvent): string {
  return event.entity_label?.split(' / ')[1] ?? event.entity_label ?? ''
}

function fieldValue(field: string, value: unknown): string {
  if (field === 'priority') return PRIORITY[value as SamplePriority]?.label ?? text(value)
  if (field === 'origin') return ORIGIN[value as SampleOrigin] ?? text(value)
  return text(value)
}

const STATUS_TITLE: Record<string, string> = {
  AWAITING_REVIEW: 'Enviada para revisão',
  APPROVED: 'Amostra aprovada',
  REJECTED: 'Amostra reprovada',
  CANCELLED: 'Amostra cancelada',
}

export function describeEvent(event: TimelineEvent): EventDescription {
  const before = values(event.old_value)
  const after = values(event.new_value)
  const reason = event.reason ? [`Justificativa: ${event.reason}`] : []

  switch (event.action) {
    case 'SAMPLE_CREATED':
      return {
        title: 'Amostra registrada',
        details: [
          `Produto ${text(after.product)} · cliente ${text(after.client)} · lote ${text(after.lot_number)}`,
        ],
        tone: 'info',
      }
    case 'TESTS_ASSIGNED': {
      const tests = Array.isArray(after.tests) ? after.tests.join(', ') : ''
      return {
        title: `Testes atribuídos: ${tests}`,
        details: [after.automatic ? 'Plano analítico do produto' : 'Atribuição manual'],
        tone: 'neutral',
      }
    }
    case 'SAMPLE_STATUS_CHANGED': {
      const from = String(before.status ?? '')
      const to = String(after.status ?? '')
      const title =
        to === 'IN_ANALYSIS'
          ? from === 'AWAITING_REVIEW'
            ? 'Devolvida para análise'
            : 'Análise iniciada'
          : (STATUS_TITLE[to] ?? 'Status alterado')
      const tone: EventTone =
        to === 'APPROVED'
          ? 'success'
          : to === 'REJECTED'
            ? 'danger'
            : from === 'AWAITING_REVIEW' && to === 'IN_ANALYSIS'
              ? 'warning'
              : 'neutral'
      return {
        title,
        details: [`${sampleStatusLabel(from)} → ${sampleStatusLabel(to)}`, ...reason],
        tone,
      }
    }
    case 'RESULT_ENTERED': {
      const oos = after.spec_status === 'OOS'
      const origin = event.actor_type === 'INSTRUMENT' ? 'enviado pelo equipamento' : 'lançamento manual'
      return {
        title: `Resultado de ${testOf(event)}: ${formatDecimal(text(after.value))} ${text(after.unit)}`,
        details: [`${oos ? 'Fora da especificação' : 'Dentro da especificação'} · ${origin}`],
        tone: oos ? 'danger' : 'success',
      }
    }
    case 'RESULT_AMENDED': {
      const oos = after.spec_status === 'OOS'
      return {
        title:
          `${testOf(event)} corrigido: ${formatDecimal(text(before.value))} → ` +
          `${formatDecimal(text(after.value))} ${text(after.unit)}`,
        details: [
          `${before.spec_status === 'OOS' ? 'Valor anterior fora da especificação' : 'Valor anterior dentro da especificação'}` +
            ` · novo valor ${oos ? 'fora' : 'dentro'} da especificação`,
          ...reason,
        ],
        tone: oos ? 'danger' : 'warning',
      }
    }
    case 'TEST_CANCELLED':
      return { title: `Teste ${testOf(event)} cancelado`, details: reason, tone: 'neutral' }
    case 'SAMPLE_UPDATED': {
      const changes = Object.keys(after).map(
        (field) =>
          `${FIELD_LABEL[field] ?? field}: ${fieldValue(field, before[field])} → ${fieldValue(field, after[field])}`,
      )
      return { title: 'Dados de registro alterados', details: changes, tone: 'neutral' }
    }
    case 'INSTRUMENT_MESSAGE_REJECTED':
      return {
        title: `Leitura recusada: ${text(after.test)} = ${formatDecimal(text(after.result))} ${text(after.unit)}`,
        details: [`${text(after.error_code)}: ${text(event.reason)}`],
        tone: 'warning',
      }
    case 'REPORT_GENERATED': {
      const hash = typeof after.content_hash === 'string' ? after.content_hash : ''
      return {
        title: `Relatório emitido (${text(after.format)})`,
        details: hash ? [`Impressão digital ${hash.slice(0, 12)}…`] : [],
        tone: 'info',
      }
    }
    default:
      return { title: auditActionLabel(event.action), details: reason, tone: 'neutral' }
  }
}
