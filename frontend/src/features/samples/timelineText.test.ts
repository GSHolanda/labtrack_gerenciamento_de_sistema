import { describe, expect, it } from 'vitest'

import { timelineEvent } from '../../test/fixtures'
import { describeEvent } from './timelineText'

describe('describeEvent', () => {
  it('resultado de equipamento fora da especificação', () => {
    const description = describeEvent(
      timelineEvent({
        actor_type: 'INSTRUMENT',
        actor_name: 'PH-METER-01',
        new_value: { value: '8.1', unit: 'pH', spec_status: 'OOS', source: 'INSTRUMENT' },
        has_oos: true,
      }),
    )
    expect(description.title).toBe('Resultado de PH: 8,1 pH')
    expect(description.details).toEqual(['Fora da especificação · enviado pelo equipamento'])
    expect(description.tone).toBe('danger')
  })

  it('correção mostra valor anterior, novo e justificativa', () => {
    const description = describeEvent(
      timelineEvent({
        action: 'RESULT_AMENDED',
        old_value: { value: '7.3', spec_status: 'OOS' },
        new_value: { value: '7.1', unit: 'pH', spec_status: 'IN_SPEC', source: 'MANUAL' },
        reason: 'Erro de transcrição',
        is_correction: true,
        has_oos: true,
      }),
    )
    expect(description.title).toBe('PH corrigido: 7,3 → 7,1 pH')
    expect(description.details).toContain('Justificativa: Erro de transcrição')
    expect(description.tone).toBe('warning')
  })

  it.each([
    ['RECEIVED', 'IN_ANALYSIS', 'Análise iniciada', 'neutral'],
    ['AWAITING_REVIEW', 'IN_ANALYSIS', 'Devolvida para análise', 'warning'],
    ['AWAITING_REVIEW', 'APPROVED', 'Amostra aprovada', 'success'],
    ['AWAITING_REVIEW', 'REJECTED', 'Amostra reprovada', 'danger'],
  ])('status %s → %s: %s', (from, to, title, tone) => {
    const description = describeEvent(
      timelineEvent({
        action: 'SAMPLE_STATUS_CHANGED',
        old_value: { status: from },
        new_value: { status: to },
      }),
    )
    expect(description.title).toBe(title)
    expect(description.tone).toBe(tone)
  })

  it('mensagem recusada de equipamento', () => {
    const description = describeEvent(
      timelineEvent({
        action: 'INSTRUMENT_MESSAGE_REJECTED',
        actor_type: 'INSTRUMENT',
        new_value: { error_code: 'UNIT_MISMATCH', test: 'PH', result: '6.1', unit: 'mV' },
        reason: 'Unidade diferente da especificada.',
      }),
    )
    expect(description.title).toBe('Leitura recusada: PH = 6,1 mV')
    expect(description.details).toEqual(['UNIT_MISMATCH: Unidade diferente da especificada.'])
  })

  it('alteração de dados de registro lista campos com rótulos', () => {
    const description = describeEvent(
      timelineEvent({
        action: 'SAMPLE_UPDATED',
        old_value: { priority: 'NORMAL' },
        new_value: { priority: 'URGENT' },
      }),
    )
    expect(description.details).toEqual(['prioridade: Normal → Urgente'])
  })

  it('emissão do relatório mostra o início da impressão digital', () => {
    const description = describeEvent(
      timelineEvent({
        action: 'REPORT_GENERATED',
        new_value: { format: 'PDF', status: 'APPROVED', content_hash: 'c47f4806874b92df843fd802' },
      }),
    )
    expect(description.title).toBe('Relatório emitido (PDF)')
    expect(description.details).toEqual(['Impressão digital c47f4806874b…'])
    expect(description.tone).toBe('info')
  })
})
