function TeamCardSkeleton() {
  return (
    <div className="min-h-36 animate-pulse rounded-xl border border-slate-200 bg-white p-4 motion-reduce:animate-none">
      <div className="flex items-start justify-between gap-3">
        <div className="h-6 w-2/3 rounded bg-slate-200" />
        <div className="size-5 rounded bg-slate-200" />
      </div>
      <div className="mt-3 h-6 w-16 rounded bg-slate-200" />
      <div className="mt-7 h-5 w-1/3 border-t border-slate-200 pt-3" />
    </div>
  )
}

export default function TeamPageLoadingSkeleton() {
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">Loading teams</span>
      <div aria-hidden="true" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }, (_, index) => (
          <TeamCardSkeleton key={index} />
        ))}
      </div>
    </div>
  )
}
