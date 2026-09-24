// Papéis de cor dos gráficos. Valores da paleta de referência, validados contra a
// superfície branca dos painéis (azul × laranja: ΔE CVD 24,7). Verde × vermelho foi
// reprovado para séries lado a lado (ΔE 4,1 em deuteranopia), por isso aprovadas e
// reprovadas usam azul e laranja; o significado vem da legenda e dos rótulos.

export const CHART = {
  series1: '#2a78d6', // azul: aprovadas, série única
  series2: '#eb6834', // laranja: reprovadas
  critical: '#d03b3b', // status crítico: somente para OOS
  surface: '#ffffff',
  grid: '#e2e8f0',
  axis: '#cbd5e1',
  textMuted: '#64748b',
  text: '#0f172a',
} as const

export const AXIS_TICK = { fill: CHART.textMuted, fontSize: 12 }
