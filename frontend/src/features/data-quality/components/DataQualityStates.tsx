interface DataQualityEmptyStateProps {
  filtered?: boolean
}

interface DataQualityErrorStateProps {
  hasRetainedResults: boolean
  message: string
  onRetry: () => void
}

const loadingFindingRows = ['first', 'second'] as const

export function DataQualitySummaryLoadingState() {
  return (
    <section
      aria-hidden="true"
      className="overflow-hidden rounded-xl border border-slate-200 bg-white"
      data-testid="data-quality-summary-skeleton"
    >
      <div className="grid divide-y divide-slate-200 sm:grid-cols-4 sm:divide-x sm:divide-y-0">
        {Array.from({ length: 4 }, (_, index) => (
          <div
            key={index}
            className="animate-pulse px-5 py-4 motion-reduce:animate-none"
          >
            <div className="h-5 w-16 rounded bg-slate-200" />
            <div className="mt-1 h-8 w-8 rounded bg-slate-100" />
          </div>
        ))}
      </div>
    </section>
  )
}

export function DataQualityLoadingState() {
  return (
    <div
      aria-label="Loading current academy health"
      aria-busy="true"
      className="overflow-hidden rounded-xl border border-slate-200 bg-white"
    >
      <p className="sr-only">Loading current academy health…</p>
      <div aria-hidden="true" className="divide-y divide-slate-200">
        {loadingFindingRows.map((row) => (
          <div
            key={row}
            className="animate-pulse px-5 py-5 motion-reduce:animate-none sm:px-6"
            data-testid="data-quality-finding-skeleton"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="h-5 w-2/5 rounded bg-slate-200" />
                <div className="mt-1 h-7 w-3/5 rounded bg-slate-200" />
              </div>
              <div className="h-7 w-20 shrink-0 rounded-md bg-slate-100" />
            </div>
            <div className="mt-3 flex h-6 items-center">
              <div className="h-4 w-4/5 rounded bg-slate-100" />
            </div>
            <div className="mt-3 flex h-6 items-center">
              <div className="h-4 w-3/5 rounded bg-slate-100" />
            </div>
            <div className="mt-4 h-11 w-full rounded-lg bg-slate-100 sm:w-40" />
          </div>
        ))}
      </div>
    </div>
  )
}

export function DataQualityEmptyState({ filtered = false }: DataQualityEmptyStateProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-6 py-10 text-center">
      <h2 className="text-lg font-bold text-slate-900">
        {filtered ? 'No findings match these filters' : 'No data quality issues found'}
      </h2>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-600">
        {filtered
          ? 'Try clearing a filter to review the rest of the academy.'
          : 'Current academy records meet the checks that are available today.'}
      </p>
    </div>
  )
}

export function DataQualityErrorState({
  hasRetainedResults,
  message,
  onRetry,
}: DataQualityErrorStateProps) {
  return (
    <div
      role="alert"
      className="mb-4 flex min-w-0 flex-col gap-3 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-950 sm:flex-row sm:items-center sm:justify-between"
    >
      <span className="min-w-0 break-words">
        {message}
        {hasRetainedResults ? ' Previous results are still shown.' : ''}
      </span>
      <button
        type="button"
        className="min-h-11 shrink-0 rounded-lg border border-rose-300 bg-white px-4 font-semibold focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
        onClick={onRetry}
      >
        Retry
      </button>
    </div>
  )
}
