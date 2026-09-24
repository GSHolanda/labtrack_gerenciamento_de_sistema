import type { SampleFilters } from '../../api/samples'

/** Fila do perfil: o que espera por quem está logado. */
export function worklistFor(userId: number | undefined, reviewer: boolean, analyst: boolean) {
  if (reviewer)
    return {
      title: 'Aguardando sua revisão',
      filters: { status: ['AWAITING_REVIEW'], sort: 'received_at', size: 8 } as SampleFilters,
      link: '/samples?status=AWAITING_REVIEW',
    }
  if (analyst && userId)
    return {
      title: 'Suas amostras em andamento',
      filters: {
        status: ['RECEIVED', 'IN_ANALYSIS'],
        responsible_id: userId,
        sort: '-priority',
        size: 8,
      } as SampleFilters,
      link: '/samples?status=RECEIVED&status=IN_ANALYSIS&mine=1',
    }
  return {
    title: 'Recebidas recentemente',
    filters: { sort: '-received_at', size: 8 } as SampleFilters,
    link: '/samples',
  }
}
