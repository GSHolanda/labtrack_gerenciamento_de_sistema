import { CircleCheck, CircleAlert, Info, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'

type AlertTone = 'info' | 'warning' | 'danger' | 'success'

const ICONS: Record<AlertTone, ReactNode> = {
  info: <Info aria-hidden />,
  warning: <TriangleAlert aria-hidden />,
  danger: <CircleAlert aria-hidden />,
  success: <CircleCheck aria-hidden />,
}

export function Alert({
  tone,
  title,
  children,
}: {
  tone: AlertTone
  title?: string
  children?: ReactNode
}) {
  return (
    <div className={`alert alert--${tone}`} role={tone === 'danger' ? 'alert' : 'status'}>
      {ICONS[tone]}
      <div>
        {title && <strong>{title}</strong>}
        {children && <div className="alert__body">{children}</div>}
      </div>
    </div>
  )
}
