interface DataQualityEmptyStateProps {
  filtered?: boolean
}

interface DataQualityErrorStateProps {
  hasRetainedResults: boolean
  message: string
  onRetry: () => void
}

export function DataQualityLoadingState() {
  return (
    <div
      aria-label="Loading current academy health"
      aria-busy="true"
      className="rounded-xl border border-slate-200 bg-white p-6"
    >
      <p className="sr-only">Loading current academy health…</p>
      <div aria-hidden="true" className="space-y-3">
        <div className="h-5 w-1/3 animate-pulse rounded bg-slate-200 motion-reduce:animate-none" />
        <div className="h-4 w-full animate-pulse rounded bg-slate-100 motion-reduce:animate-none" />
        <div className="h-4 w-4/5 animate-pulse rounded bg-slate-100 motion-reduce:animate-none" />
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
