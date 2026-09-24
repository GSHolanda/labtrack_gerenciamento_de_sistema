import { Table2 } from 'lucide-react'
import { type ReactNode, useId, useState } from 'react'

export interface LegendItem {
  label: string
  color: string
}

/**
 * Cartão de gráfico: título, legenda (duas ou mais séries) e a tabela equivalente,
 * para ler os valores sem depender de cor nem de passar o mouse.
 */
export function ChartCard({
  title,
  subtitle,
  legend,
  table,
  empty,
  children,
}: {
  title: ReactNode
  subtitle?: string
  legend?: LegendItem[]
  table: ReactNode
  empty?: string | null
  children: ReactNode
}) {
  const [showTable, setShowTable] = useState(false)
  const tableId = useId()
  return (
    <figure className="chart-card">
      <figcaption className="chart-card__header">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        <button
          type="button"
          className={showTable ? 'chip chip--active' : 'chip'}
          aria-pressed={showTable}
          aria-controls={tableId}
          onClick={() => setShowTable((value) => !value)}
        >
          <Table2 aria-hidden /> Tabela
        </button>
      </figcaption>
      {legend && legend.length > 1 && (
        <ul className="chart-legend">
          {legend.map((item) => (
            <li key={item.label}>
              <span className="chart-legend__swatch" style={{ background: item.color }} />
              {item.label}
            </li>
          ))}
        </ul>
      )}
      {empty ? (
        <p className="chart-card__empty">{empty}</p>
      ) : showTable ? (
        <div id={tableId} className="table-wrapper chart-card__table">
          {table}
        </div>
      ) : (
        <div className="chart-card__plot">{children}</div>
      )}
    </figure>
  )
}
