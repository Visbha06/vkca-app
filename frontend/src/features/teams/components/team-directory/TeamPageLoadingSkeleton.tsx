function TeamRowSkeleton() {
  return (
    <div className="grid min-h-20 animate-pulse grid-cols-[2.75rem_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-3 px-4 py-4 sm:px-5 lg:grid-cols-[2.75rem_minmax(0,1.5fr)_minmax(7rem,1fr)_minmax(7rem,0.9fr)_minmax(6.5rem,0.8fr)_1.25rem] lg:gap-x-4 motion-reduce:animate-none">
      <div className="col-start-1 row-start-1 size-11 rounded-full bg-slate-200" />
      <div className="col-start-2 row-start-1 h-5 w-2/3 rounded bg-slate-200" />
      <div className="col-start-3 row-start-1 size-5 rounded bg-slate-200 lg:col-start-6" />
      <div className="col-span-2 col-start-2 row-start-2 lg:col-span-1 lg:col-start-3 lg:row-start-1">
        <div className="h-4 w-24 rounded bg-slate-200" />
        <div className="mt-2 h-1.5 w-full rounded-full bg-slate-200" />
      </div>
      <div className="col-span-2 col-start-2 row-start-3 h-4 w-28 rounded bg-slate-200 lg:col-span-1 lg:col-start-4 lg:row-start-1" />
      <div className="col-span-2 col-start-2 row-start-4 h-4 w-24 rounded bg-slate-200 lg:col-span-1 lg:col-start-5 lg:row-start-1" />
    </div>
  )
}

export default function TeamPageLoadingSkeleton() {
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">Loading teams</span>
      <div
        aria-hidden="true"
        className="overflow-hidden rounded-xl border border-slate-200 bg-white"
      >
        <div className="hidden h-11 border-b border-slate-200 bg-slate-50 lg:block" />
        <div className="divide-y divide-slate-200">
          {Array.from({ length: 5 }, (_, index) => (
            <TeamRowSkeleton key={index} />
          ))}
        </div>
      </div>
    </div>
  )
}
