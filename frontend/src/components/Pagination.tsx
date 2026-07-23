interface PaginationProps {
  page: number
  totalPages: number
  isLoading: boolean
  onPageChange: (page: number) => void
}

const buttonClass =
  'inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-800 transition-colors hover:border-academy hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400'

export default function Pagination({
  page,
  totalPages,
  isLoading,
  onPageChange,
}: PaginationProps) {
  const pages = Array.from({ length: totalPages }, (_, index) => index + 1)

  return (
    <nav
      aria-label="Player pages"
      aria-busy={isLoading}
      className="flex flex-wrap items-center justify-center gap-2"
    >
      <button
        type="button"
        aria-label="Previous page"
        className={buttonClass}
        disabled={isLoading || page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        <span aria-hidden="true">←</span>
        <span className="sr-only">Previous</span>
      </button>
      {pages.map((pageNumber) => (
        <button
          key={pageNumber}
          type="button"
          aria-label={`Page ${pageNumber}`}
          aria-current={pageNumber === page ? 'page' : undefined}
          className={`${buttonClass} ${
            pageNumber === page
              ? 'border-slate-900 bg-slate-900 text-white hover:border-slate-900 hover:bg-slate-800'
              : ''
          }`}
          disabled={isLoading}
          onClick={() => onPageChange(pageNumber)}
        >
          {pageNumber}
        </button>
      ))}
      <button
        type="button"
        aria-label="Next page"
        className={buttonClass}
        disabled={isLoading || totalPages === 0 || page >= totalPages}
        onClick={() => onPageChange(page + 1)}
      >
        <span aria-hidden="true">→</span>
        <span className="sr-only">Next</span>
      </button>
    </nav>
  )
}
