import type { ReactNode } from 'react'

import {
  INSTRUMENT_STATUS,
  MESSAGE_STATUS,
  PRIORITY,
  SAMPLE_STATUS,
  SPEC_STATUS,
  TEST_STATUS,
  type Tone,
} from '../lib/labels'
import type {
  InstrumentMessageStatus,
  InstrumentStatus,
  SamplePriority,
  SampleStatus,
  SampleTestStatus,
  SpecStatus,
} from '../types/api'

export function Badge({
  tone = 'neutral',
  children,
  icon,
  title,
}: {
  tone?: Tone
  children: ReactNode
  icon?: ReactNode
  title?: string
}) {
  return (
    <span className={`badge badge--${tone}`} title={title}>
      {icon}
      {children}
    </span>
  )
}

export function SampleStatusBadge({ status }: { status: SampleStatus }) {
  const { label, tone } = SAMPLE_STATUS[status]
  return <Badge tone={tone}>{label}</Badge>
}

export function PriorityBadge({ priority }: { priority: SamplePriority }) {
  const { label, tone } = PRIORITY[priority]
  return <Badge tone={tone}>{label}</Badge>
}

export function TestStatusBadge({ status }: { status: SampleTestStatus }) {
  const { label, tone } = TEST_STATUS[status]
  return <Badge tone={tone}>{label}</Badge>
}

export function SpecBadge({ status, short = false }: { status: SpecStatus; short?: boolean }) {
  const { label, tone } = SPEC_STATUS[status]
  return (
    <Badge tone={tone} title={label}>
      {short ? (status === 'OOS' ? 'OOS' : 'Conforme') : label}
    </Badge>
  )
}

export function InstrumentStatusBadge({ status }: { status: InstrumentStatus }) {
  const { label, tone } = INSTRUMENT_STATUS[status]
  return <Badge tone={tone}>{label}</Badge>
}

export function MessageStatusBadge({ status }: { status: InstrumentMessageStatus }) {
  const { label, tone } = MESSAGE_STATUS[status]
  return <Badge tone={tone}>{label}</Badge>
}

export function ActiveBadge({ active }: { active: boolean }) {
  return <Badge tone={active ? 'success' : 'muted'}>{active ? 'Ativo' : 'Inativo'}</Badge>
}
