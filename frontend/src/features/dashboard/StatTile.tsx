import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { Delta } from './dashboardFormat'

const DIRECTION_ICON = { up: ArrowUpRight, down: ArrowDownRight, flat: Minus }
const TONE_LABEL = { good: 'melhora', bad: 'piora', neutral: '' }

/** Indicador: rótulo, valor e, opcionalmente, variação contra o período anterior. */
export function StatTile({
  label,
  value,
  hint,
  delta,
  comparison,
  to,
  alert = false,
  icon,
}: {
  label: string
  value: string
  hint?: string
  delta?: Delta | null
  comparison?: string
  to?: string
  alert?: boolean
  icon?: ReactNode
}) {
  const content = (
    <>
      <span className="stat-tile__label">
        {icon}
        {label}
      </span>
      <strong className="stat-tile__value">{value}</strong>
      {delta && (
        <span className={`stat-tile__delta stat-tile__delta--${delta.tone}`}>
          {(() => {
            const Icon = DIRECTION_ICON[delta.direction]
            return <Icon aria-hidden />
          })()}
          {delta.text}
          {comparison && <span className="stat-tile__comparison"> {comparison}</span>}
          {TONE_LABEL[delta.tone] && <span className="sr-only"> ({TONE_LABEL[delta.tone]})</span>}
        </span>
      )}
      {hint && <span className="stat-tile__hint">{hint}</span>}
    </>
  )
  const className = alert ? 'stat-tile stat-tile--alert' : 'stat-tile'
  return to ? (
    <Link to={to} className={`${className} stat-tile--link`}>
      {content}
    </Link>
  ) : (
    <div className={className}>{content}</div>
  )
}
