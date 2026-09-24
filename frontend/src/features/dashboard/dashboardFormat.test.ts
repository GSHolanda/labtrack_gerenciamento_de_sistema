import { describe, expect, it } from 'vitest'

import { bucketLabel, bucketTitle, delta, formatHours, formatPercent } from './dashboardFormat'

describe('formatação do dashboard', () => {
  it.each([
    [null, '—'],
    [5.24, '5,2 h'],
    [47.9, '47,9 h'],
    [50, '2 d 2 h'],
    [72, '3 d'],
  ])('horas %s → %s', (hours, expected) => {
    expect(formatHours(hours)).toBe(expected)
  })

  it('percentual com uma casa', () => {
    expect(formatPercent(0.8333)).toBe('83,3%')
    expect(formatPercent(null)).toBe('—')
  })

  it('rótulos dos intervalos', () => {
    expect(bucketLabel('2026-09-21', 'week')).toBe('21/09')
    expect(bucketTitle('2026-09-21', 'week')).toBe('Semana de 21/09/2026')
    expect(bucketLabel('2026-01-01', 'month')).toBe('jan/26')
    expect(bucketTitle('2026-09-01', 'month')).toBe('set/2026')
  })
})

describe('variação contra o período anterior', () => {
  it('subir é bom ou ruim conforme o indicador', () => {
    expect(delta(12, 10, 'up')).toEqual({ text: '+2', direction: 'up', tone: 'good' })
    expect(delta(3, 1, 'down')).toEqual({ text: '+2', direction: 'up', tone: 'bad' })
    expect(delta(1, 3, 'down')).toEqual({ text: '−2', direction: 'down', tone: 'good' })
    expect(delta(5, 3, 'none')?.tone).toBe('neutral')
  })

  it('taxas em pontos percentuais e tempos em horas', () => {
    expect(delta(0.9, 0.8, 'up', 'rate')?.text).toBe('+10 p.p.')
    expect(delta(20, 26.5, 'down', 'hours')).toEqual({
      text: '−6,5 h',
      direction: 'down',
      tone: 'good',
    })
  })

  it('sem base de comparação não mostra variação', () => {
    expect(delta(0.8, null, 'up', 'rate')).toBeNull()
    expect(delta(4, 4, 'up')).toEqual({ text: 'sem variação', direction: 'flat', tone: 'neutral' })
  })
})
