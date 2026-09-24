import { ChevronLeft, ChevronRight } from 'lucide-react'

export function Pagination({
  page,
  pages,
  total,
  size,
  onPage,
}: {
  page: number
  pages: number
  total: number
  size: number
  onPage: (page: number) => void
}) {
  if (total === 0) return null
  const first = (page - 1) * size + 1
  const last = Math.min(page * size, total)
  return (
    <nav className="pagination" aria-label="Paginação">
      <span>
        {first}–{last} de {total}
      </span>
      <div className="pagination__buttons">
        <button
          type="button"
          className="icon-button"
          onClick={() => onPage(page - 1)}
          disabled={page <= 1}
          aria-label="Página anterior"
        >
          <ChevronLeft aria-hidden />
        </button>
        <span>
          Página {page} de {Math.max(pages, 1)}
        </span>
        <button
          type="button"
          className="icon-button"
          onClick={() => onPage(page + 1)}
          disabled={page >= pages}
          aria-label="Próxima página"
        >
          <ChevronRight aria-hidden />
        </button>
      </div>
    </nav>
  )
}
