import { Wifi, WifiOff } from 'lucide-react'

import { Badge } from '../../components/Badge'
import { formatDate, formatRelative } from '../../lib/format'
import type { Instrument } from '../../types/api'

export function ConnectionBadge({ instrument }: { instrument: Instrument }) {
  return instrument.online ? (
    <Badge tone="success" icon={<Wifi aria-hidden />}>
      Online
    </Badge>
  ) : (
    <Badge
      tone="muted"
      icon={<WifiOff aria-hidden />}
      title={instrument.last_communication_at ? undefined : 'Nunca se comunicou'}
    >
      {instrument.last_communication_at
        ? `Offline · ${formatRelative(instrument.last_communication_at)}`
        : 'Offline'}
    </Badge>
  )
}

export function CalibrationBadge({ instrument }: { instrument: Instrument }) {
  return (
    <Badge tone={instrument.calibration_valid ? 'success' : 'danger'}>
      {instrument.calibration_valid ? 'Válida até ' : 'Vencida em '}
      {formatDate(instrument.calibration_due_date)}
    </Badge>
  )
}
