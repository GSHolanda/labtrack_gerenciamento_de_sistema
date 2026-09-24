import { useInfiniteQuery } from '@tanstack/react-query'
import {
  Ban,
  CircleCheck,
  CircleX,
  ClipboardList,
  Cpu,
  FlaskConical,
  ListChecks,
  Pencil,
  Play,
  Send,
  TriangleAlert,
  Undo2,
} from 'lucide-react'
import type { ReactNode } from 'react'

import { queryKeys } from '../../api/queryKeys'
import { samplesApi } from '../../api/samples'
import { Button } from '../../components/Button'
import { EmptyState, ErrorState, LoadingState } from '../../components/States'
import { formatLongDate, formatTime, localDayKey } from '../../lib/format'
import { ACTOR_TYPE } from '../../lib/labels'
import type { TimelineEvent } from '../../types/api'
import { describeEvent } from './timelineText'

function iconFor(event: TimelineEvent): ReactNode {
  const status = (event.new_value as { status?: string } | null)?.status
  switch (event.action) {
    case 'SAMPLE_CREATED':
      return <FlaskConical />
    case 'TESTS_ASSIGNED':
      return <ListChecks />
    case 'SAMPLE_STATUS_CHANGED':
      if (status === 'APPROVED') return <CircleCheck />
      if (status === 'REJECTED') return <CircleX />
      if (status === 'CANCELLED') return <Ban />
      if (status === 'AWAITING_REVIEW') return <Send />
      return (event.old_value as { status?: string } | null)?.status === 'AWAITING_REVIEW' ? (
        <Undo2 />
      ) : (
        <Play />
      )
    case 'RESULT_ENTERED':
      return event.has_oos ? <TriangleAlert /> : <ClipboardList />
    case 'RESULT_AMENDED':
      return <Pencil />
    case 'INSTRUMENT_MESSAGE_REJECTED':
      return <Cpu />
    default:
      return <ClipboardList />
  }
}

/** Sample Timeline: histórico cronológico derivado do audit trail (mesma fonte). */
export function SampleTimeline({ sampleId }: { sampleId: number }) {
  const timeline = useInfiniteQuery({
    queryKey: queryKeys.timeline(sampleId),
    queryFn: ({ pageParam }) => samplesApi.timeline(sampleId, pageParam),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.page < last.pages ? last.page + 1 : undefined),
  })

  if (timeline.isPending) return <LoadingState label="Carregando a timeline…" />
  if (timeline.isError) return <ErrorState error={timeline.error} onRetry={() => timeline.refetch()} />

  const events = timeline.data.pages.flatMap((page) => page.items)
  if (events.length === 0) return <EmptyState title="Nenhum evento registrado" />

  const days: { key: string; label: string; events: TimelineEvent[] }[] = []
  for (const event of events) {
    const key = localDayKey(event.occurred_at)
    const last = days.at(-1)
    if (last?.key === key) last.events.push(event)
    else days.push({ key, label: formatLongDate(event.occurred_at), events: [event] })
  }

  return (
    <div className="timeline">
      {days.map((day) => (
        <section key={day.key} className="timeline__day">
          <h3>{day.label}</h3>
          <ol>
            {day.events.map((event) => {
              const description = describeEvent(event)
              // Correção que resolveu um OOS: amarelo (correção), com a etiqueta OOS mantida.
              const tone = event.has_oos && !event.is_correction ? 'danger' : description.tone
              return (
                <li key={event.id} className={`timeline__item timeline__item--${tone}`}>
                  <span className="timeline__icon" aria-hidden>
                    {iconFor(event)}
                  </span>
                  <div className="timeline__content">
                    <div className="timeline__meta">
                      <time dateTime={event.occurred_at}>{formatTime(event.occurred_at)}</time>
                      <span>
                        {event.actor_name}
                        {event.actor_type !== 'USER' && ` (${ACTOR_TYPE[event.actor_type]})`}
                      </span>
                    </div>
                    <p className="timeline__title">
                      {description.title}
                      {event.is_correction && <span className="tag tag--warning">Correção</span>}
                      {event.has_oos && <span className="tag tag--danger">OOS</span>}
                    </p>
                    {description.details.map((detail) => (
                      <p key={detail} className="timeline__detail">
                        {detail}
                      </p>
                    ))}
                  </div>
                </li>
              )
            })}
          </ol>
        </section>
      ))}
      {timeline.hasNextPage && (
        <Button
          size="sm"
          variant="ghost"
          loading={timeline.isFetchingNextPage}
          onClick={() => timeline.fetchNextPage()}
        >
          Carregar eventos seguintes
        </Button>
      )}
    </div>
  )
}
