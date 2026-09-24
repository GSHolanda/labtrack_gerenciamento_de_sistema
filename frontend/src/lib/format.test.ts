import { describe, expect, it } from 'vitest'

import {
  compareDecimals,
  evaluateSpec,
  formatDate,
  formatDecimal,
  formatSpec,
  parseApiDate,
  parseDecimalInput,
} from './format'

describe('formatDecimal', () => {
  it.each([
    ['7.2100', 2, '7,21'],
    ['7.2150', 2, '7,215'], // nunca esconde dígitos registrados
    ['7', 2, '7,00'],
    ['5250.0000', 0, '5250'],
    ['0.5000', undefined, '0,5'],
    ['-0.25', 1, '-0,25'],
    ['007.10', 1, '7,1'],
  ])('%s com %s casas → %s', (value, places, expected) => {
    expect(formatDecimal(value, places)).toBe(expected)
  })

  it('mostra traço para vazio', () => {
    expect(formatDecimal(null)).toBe('—')
  })
})

describe('formatSpec', () => {
  it('formata faixa bilateral e unilateral', () => {
    expect(formatSpec('5.5000', '7.0000', 'pH', 2)).toBe('5,50 a 7,00 pH')
    expect(formatSpec(null, '0.5000', '%', 2)).toBe('≤ 0,50 %')
    expect(formatSpec('95.0000', null, '%', 1)).toBe('≥ 95,0 %')
  })
})

describe('parseDecimalInput', () => {
  it.each([
    ['7,21', '7.21'],
    ['7.21', '7.21'],
    [' -0,5 ', '-0.5'],
    ['1 020', '1020'],
  ])('%s → %s', (text, expected) => {
    expect(parseDecimalInput(text)).toBe(expected)
  })

  it.each(['', 'abc', '7,2,1', '1.234,5', '7.'])('recusa %s', (text) => {
    expect(parseDecimalInput(text)).toBeNull()
  })
})

describe('evaluateSpec (prévia de RN-16)', () => {
  it('usa limites inclusivos e comparação exata', () => {
    expect(evaluateSpec('7.0', '5.5', '7.0000')).toBe('IN_SPEC')
    expect(evaluateSpec('7.0001', '5.5', '7.0')).toBe('OOS')
    expect(evaluateSpec('5.4999', '5.5', '7.0')).toBe('OOS')
    expect(evaluateSpec('0.3', null, '0.5')).toBe('IN_SPEC')
    expect(evaluateSpec('-1', '-2', null)).toBe('IN_SPEC')
  })

  it('compara decimais sem ponto flutuante', () => {
    expect(compareDecimals('0.3', '0.1')).toBe(1)
    expect(compareDecimals('1.10', '1.1')).toBe(0)
    expect(compareDecimals('-0.5', '0.1')).toBe(-1)
  })
})

describe('datas', () => {
  it('interpreta data sem fuso como UTC', () => {
    expect(parseApiDate('2026-09-20T12:00:00').toISOString()).toBe('2026-09-20T12:00:00.000Z')
    expect(parseApiDate('2026-09-20T12:00:00Z').toISOString()).toBe('2026-09-20T12:00:00.000Z')
  })

  it('data sem hora não muda de dia com o fuso', () => {
    expect(formatDate('2026-09-12')).toBe('12/09/2026')
  })
})
