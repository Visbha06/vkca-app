interface PaginationProps {
  ariaLabel: string
  page: number
  totalPages: number
  isLoading: boolean
  onPageChange: (page: number) => void
}

const PAGE_WINDOW_SIZE = 10

const buttonBaseClass =
  'inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border px-3 text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed'
const inactiveButtonClass =
  'border-slate-300 bg-white text-slate-800 hover:border-academy hover:bg-academy/10 disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400'
const activeButtonClass =
  'border-slate-900 bg-slate-900 text-white hover:border-slate-900 hover:bg-slate-800'

export default function Pagination({
  ariaLabel,
  page,
  totalPages,
  isLoading,
  onPageChange,
}: PaginationProps) {
  const windowStart = Math.floor((page - 1) / PAGE_WINDOW_SIZE) * PAGE_WINDOW_SIZE + 1
  const windowEnd = Math.min(windowStart + PAGE_WINDOW_SIZE - 1, totalPages)
  const pages = Array.from(
    { length: Math.max(0, windowEnd - windowStart + 1) },
    (_, index) => windowStart + index,
  )
  const hasMultipleWindows = totalPages > PAGE_WINDOW_SIZE
  const previousLabel = hasMultipleWindows ? 'Previous page range' : 'Previous page'
  const nextLabel = hasMultipleWindows ? 'Next page range' : 'Next page'

  return (
    <nav
      aria-label={ariaLabel}
      aria-busy={isLoading}
      className="mx-auto grid w-fit max-w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2"
    >
      <button
        type="button"
        aria-label={previousLabel}
        className={`${buttonBaseClass} ${inactiveButtonClass}`}
        disabled={isLoading || (hasMultipleWindows ? windowStart <= 1 : page <= 1)}
        onClick={() => onPageChange(hasMultipleWindows ? windowStart - 1 : page - 1)}
      >
        <span aria-hidden="true">←</span>
        <span className="sr-only">{previousLabel}</span>
      </button>
      <div role="group" aria-label="Page numbers" data-pagination-pages className="flex min-w-0 flex-nowrap items-center gap-2 overflow-x-auto overscroll-x-contain pb-1">
        {pages.map((pageNumber) => (
          <button
            key={pageNumber}
            type="button"
            aria-label={`Page ${pageNumber}`}
            aria-current={pageNumber === page ? 'page' : undefined}
            className={`${buttonBaseClass} ${
              pageNumber === page ? activeButtonClass : inactiveButtonClass
            }`}
            disabled={isLoading}
            onClick={() => onPageChange(pageNumber)}
          >
            {pageNumber}
          </button>
        ))}
      </div>
      <button
        type="button"
        aria-label={nextLabel}
        className={`${buttonBaseClass} ${inactiveButtonClass}`}
        disabled={isLoading || totalPages === 0 || (hasMultipleWindows ? windowEnd >= totalPages : page >= totalPages)}
        onClick={() => onPageChange(hasMultipleWindows ? windowEnd + 1 : page + 1)}
      >
        <span aria-hidden="true">→</span>
        <span className="sr-only">{nextLabel}</span>
      </button>
    </nav>
  )
}
