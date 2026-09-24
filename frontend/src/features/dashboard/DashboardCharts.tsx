import { TriangleAlert } from 'lucide-react'
import {
  Bar,
  BarChart,
  type BarShapeProps,
  CartesianGrid,
  LabelList,
  Line,
  LineChart,
  Rectangle,
  ResponsiveContainer,
  Tooltip,
  type TooltipContentProps,
  XAxis,
  YAxis,
} from 'recharts'

import { SAMPLE_STATUS } from '../../lib/labels'
import type { DashboardCharts as Charts, Granularity } from '../../types/api'
import { ChartCard } from './ChartCard'
import { AXIS_TICK, CHART } from './chartTheme'
import {
  GRANULARITY_LABEL,
  bucketLabel,
  bucketTitle,
  formatCount,
  formatPercent,
} from './dashboardFormat'

interface ThroughputRow {
  label: string
  title: string
  approved: number
  rejected: number
  total: number
  rate: number | null // 0 a 100
}

const PLOT_HEIGHT = 260
const MARGIN = { top: 12, right: 16, bottom: 4, left: 0 }

export default function DashboardCharts({ charts }: { charts: Charts }) {
  const rows: ThroughputRow[] = charts.throughput.map((point) => ({
    label: bucketLabel(point.bucket, charts.granularity),
    title: bucketTitle(point.bucket, charts.granularity),
    approved: point.approved,
    rejected: point.rejected,
    total: point.approved + point.rejected,
    rate: point.approval_rate === null ? null : Math.round(point.approval_rate * 1000) / 10,
  }))
  const decided = rows.some((row) => row.total > 0)

  return (
    <div className="chart-grid">
      <ThroughputChart rows={rows} granularity={charts.granularity} empty={!decided} />
      <ApprovalRateChart rows={rows} granularity={charts.granularity} empty={!decided} />
      <StatusChart charts={charts} />
      <OosByTestChart charts={charts} />
    </div>
  )
}

// --- Decisões por intervalo (colunas empilhadas) --------------------------------------

/** Espaço de 2px na cor da superfície entre segmentos; ponta arredondada só no topo. */
function segment(key: 'approved' | 'rejected') {
  return function Segment(props: BarShapeProps) {
    const row = props.payload as ThroughputRow
    const isTop = key === 'rejected' || row.rejected === 0
    return (
      <Rectangle
        x={props.x}
        y={props.y}
        width={props.width}
        height={props.height}
        fill={props.fill}
        stroke={CHART.surface}
        strokeWidth={2}
        radius={isTop ? [4, 4, 0, 0] : 0}
      />
    )
  }
}

function ThroughputTooltip({ active, payload }: TooltipContentProps) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload as ThroughputRow
  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip__title">{row.title}</p>
      <ul>
        <li>
          <span className="chart-tooltip__key" style={{ background: CHART.series1 }} />
          <strong>{formatCount(row.approved)}</strong> aprovadas
        </li>
        <li>
          <span className="chart-tooltip__key" style={{ background: CHART.series2 }} />
          <strong>{formatCount(row.rejected)}</strong> reprovadas
        </li>
      </ul>
      <p className="chart-tooltip__note">
        Taxa de aprovação: {row.rate === null ? '—' : `${String(row.rate).replace('.', ',')}%`}
      </p>
    </div>
  )
}

function ThroughputChart({
  rows,
  granularity,
  empty,
}: {
  rows: ThroughputRow[]
  granularity: Granularity
  empty: boolean
}) {
  return (
    <ChartCard
      title="Amostras decididas"
      subtitle={`Aprovações e reprovações ${GRANULARITY_LABEL[granularity]}, pela data da decisão`}
      legend={[
        { label: 'Aprovadas', color: CHART.series1 },
        { label: 'Reprovadas', color: CHART.series2 },
      ]}
      empty={empty ? 'Nenhuma amostra aprovada ou reprovada no período.' : null}
      table={
        <table className="table">
          <thead>
            <tr>
              <th>Período</th>
              <th>Aprovadas</th>
              <th>Reprovadas</th>
              <th>Taxa de aprovação</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.title}>
                <td>{row.title}</td>
                <td>{formatCount(row.approved)}</td>
                <td>{formatCount(row.rejected)}</td>
                <td>{row.rate === null ? '—' : formatPercent(row.rate / 100)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <ResponsiveContainer width="100%" height={PLOT_HEIGHT}>
        <BarChart data={rows} margin={MARGIN} barCategoryGap="28%">
          <CartesianGrid vertical={false} stroke={CHART.grid} />
          <XAxis
            dataKey="label"
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={{ stroke: CHART.axis }}
            interval="preserveStartEnd"
            minTickGap={12}
          />
          <YAxis
            allowDecimals={false}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={false}
            width={36}
          />
          <Tooltip content={ThroughputTooltip} cursor={{ fill: 'rgba(15, 23, 42, 0.05)' }} />
          <Bar
            dataKey="approved"
            name="Aprovadas"
            stackId="decisions"
            fill={CHART.series1}
            maxBarSize={24}
            shape={segment('approved')}
            isAnimationActive={false}
          />
          <Bar
            dataKey="rejected"
            name="Reprovadas"
            stackId="decisions"
            fill={CHART.series2}
            maxBarSize={24}
            shape={segment('rejected')}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

// --- Taxa de aprovação (linha, série única, eixo 0 a 100%) ------------------------------

/** Mostra o intervalo mesmo sem decisões (a linha fica em branco, o tooltip explica). */
function rateTooltip(rows: ThroughputRow[]) {
  return function RateTooltip({ active, activeIndex }: TooltipContentProps) {
    const row = active && activeIndex !== undefined ? rows[Number(activeIndex)] : undefined
    if (!row) return null
    return (
      <div className="chart-tooltip">
        <p className="chart-tooltip__title">{row.title}</p>
        {row.rate === null ? (
          <p>Sem decisões neste intervalo</p>
        ) : (
          <>
            <p>
              <strong>{formatPercent(row.rate / 100)}</strong> aprovadas
            </p>
            <p className="chart-tooltip__note">
              {formatCount(row.approved)} de {formatCount(row.total)} decididas
            </p>
          </>
        )}
      </div>
    )
  }
}

function ApprovalRateChart({
  rows,
  granularity,
  empty,
}: {
  rows: ThroughputRow[]
  granularity: Granularity
  empty: boolean
}) {
  const lastIndex = rows.findLastIndex((row) => row.rate !== null)
  return (
    <ChartCard
      title="Taxa de aprovação"
      subtitle={`Aprovadas sobre decididas, ${GRANULARITY_LABEL[granularity]}; intervalos sem decisão ficam em branco`}
      empty={empty ? 'Sem decisões no período para calcular a taxa.' : null}
      table={
        <table className="table">
          <thead>
            <tr>
              <th>Período</th>
              <th>Taxa de aprovação</th>
              <th>Decididas</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.title}>
                <td>{row.title}</td>
                <td>{row.rate === null ? '—' : formatPercent(row.rate / 100)}</td>
                <td>{formatCount(row.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <ResponsiveContainer width="100%" height={PLOT_HEIGHT}>
        <LineChart data={rows} margin={{ ...MARGIN, right: 40 }}>
          <CartesianGrid vertical={false} stroke={CHART.grid} />
          <XAxis
            dataKey="label"
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={{ stroke: CHART.axis }}
            interval="preserveStartEnd"
            minTickGap={12}
          />
          <YAxis
            domain={[0, 100]}
            ticks={[0, 25, 50, 75, 100]}
            tickFormatter={(value: number) => `${value}%`}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={false}
            width={44}
          />
          <Tooltip content={rateTooltip(rows)} cursor={{ stroke: CHART.axis, strokeWidth: 1 }} />
          <Line
            dataKey="rate"
            name="Taxa de aprovação"
            type="linear"
            stroke={CHART.series1}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            connectNulls={false}
            dot={{ r: 4, fill: CHART.series1, stroke: CHART.surface, strokeWidth: 2 }}
            activeDot={{ r: 6, fill: CHART.series1, stroke: CHART.surface, strokeWidth: 2 }}
            isAnimationActive={false}
          >
            <LabelList
              dataKey="rate"
              content={(props) => {
                if (props.index !== lastIndex || props.value === null) return null
                return (
                  <text
                    x={Number(props.x) + 8}
                    y={Number(props.y) + 4}
                    fill={CHART.text}
                    fontSize={12}
                    fontWeight={600}
                  >
                    {formatPercent(Number(props.value) / 100)}
                  </text>
                )
              }}
            />
          </Line>
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

// --- Barras horizontais de série única -----------------------------------------------------

interface HorizontalRow {
  label: string
  value: number
  tip: string
}

function HorizontalBars({
  rows,
  color,
  name,
}: {
  rows: HorizontalRow[]
  color: string
  name: string
}) {
  const height = rows.length * 36 + 16
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 128, bottom: 4, left: 0 }}>
        <XAxis type="number" hide allowDecimals={false} domain={[0, 'dataMax']} />
        <YAxis
          type="category"
          dataKey="label"
          tick={{ ...AXIS_TICK, fill: CHART.text }}
          tickLine={false}
          axisLine={{ stroke: CHART.axis }}
          width={150}
        />
        <Tooltip
          cursor={{ fill: 'rgba(15, 23, 42, 0.05)' }}
          content={({ active, payload }: TooltipContentProps) => {
            if (!active || !payload?.length) return null
            const row = payload[0].payload as HorizontalRow
            return (
              <div className="chart-tooltip">
                <p className="chart-tooltip__title">{row.label}</p>
                <p>
                  <strong>{row.tip}</strong>
                </p>
              </div>
            )
          }}
        />
        <Bar
          dataKey="value"
          name={name}
          fill={color}
          barSize={18}
          radius={[0, 4, 4, 0]}
          isAnimationActive={false}
        >
          <LabelList dataKey="tip" position="right" fill={CHART.textMuted} fontSize={12} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function StatusChart({ charts }: { charts: Charts }) {
  const rows = charts.by_status.map((item) => ({
    label: SAMPLE_STATUS[item.status].label,
    value: item.count,
    tip: formatCount(item.count),
  }))
  const total = rows.reduce((sum, row) => sum + row.value, 0)
  return (
    <ChartCard
      title="Amostras recebidas por status"
      subtitle="Situação atual das amostras recebidas no período"
      empty={total === 0 ? 'Nenhuma amostra recebida no período.' : null}
      table={
        <table className="table">
          <thead>
            <tr>
              <th>Status</th>
              <th>Amostras</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label}>
                <td>{row.label}</td>
                <td>{row.tip}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <HorizontalBars rows={rows} color={CHART.series1} name="Amostras" />
    </ChartCard>
  )
}

function OosByTestChart({ charts }: { charts: Charts }) {
  const tests = charts.oos_by_test
  // O gráfico mostra só testes com OOS; a tabela traz todos, inclusive os sem ocorrência.
  const withOos = tests.filter((test) => test.oos > 0)
  const rows = withOos.slice(0, 8).map((test) => ({
    label: test.test_name,
    value: test.oos,
    tip: `${formatCount(test.oos)} de ${formatCount(test.results)} (${formatPercent(test.oos_rate)})`,
  }))
  const others = tests.length - rows.length
  return (
    <ChartCard
      title={
        <span className="with-icon">
          <TriangleAlert aria-hidden className="text-danger" /> Resultados OOS por teste
        </span>
      }
      subtitle={
        'Fora da especificação sobre os resultados registrados no período, inclusive os ' +
        `depois corrigidos${others > 0 ? `; os outros ${others} teste(s) estão na tabela` : ''}`
      }
      empty={
        tests.length === 0
          ? 'Nenhum resultado registrado no período.'
          : withOos.length === 0
            ? `Nenhum resultado OOS entre os ${formatCount(tests.reduce((sum, test) => sum + test.results, 0))} registrados no período.`
            : null
      }
      table={
        <table className="table">
          <thead>
            <tr>
              <th>Teste</th>
              <th>Resultados</th>
              <th>OOS</th>
              <th>% OOS</th>
            </tr>
          </thead>
          <tbody>
            {tests.map((test) => (
              <tr key={test.test_code}>
                <td>
                  {test.test_name} <code>{test.test_code}</code>
                </td>
                <td>{formatCount(test.results)}</td>
                <td>{formatCount(test.oos)}</td>
                <td>{formatPercent(test.oos_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <HorizontalBars rows={rows} color={CHART.critical} name="Resultados OOS" />
    </ChartCard>
  )
}
