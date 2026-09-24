import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import type { ReactNode } from 'react'

/** Cabeçalho que alterna a ordenação "campo" ↔ "-campo" (formato da API). */
export function SortableHeader({
  field,
  sort,
  onSort,
  children,
}: {
  field: string
  sort: string | undefined
  onSort: (sort: string) => void
  children: ReactNode
}) {
  const active = sort === field || sort === `-${field}`
  const descending = sort === `-${field}`
  const next = active && !descending ? `-${field}` : field
  const Icon = !active ? ArrowUpDown : descending ? ArrowDown : ArrowUp
  return (
    <th aria-sort={active ? (descending ? 'descending' : 'ascending') : 'none'}>
      <button type="button" className="sort-button" onClick={() => onSort(next)}>
        {children}
        <Icon aria-hidden className={active ? 'sort-button__icon--active' : undefined} />
      </button>
    </th>
  )
}
