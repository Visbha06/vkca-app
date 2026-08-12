export default function DashboardLoadingState() {
  return (
    <div
      role="status"
      aria-label="Loading dashboard"
      className="py-8"
    >
      <span className="sr-only">Loading your live dashboard…</span>
      <div
        aria-hidden="true"
        className="space-y-8 motion-safe:animate-pulse"
      >
        <div className="grid overflow-hidden rounded-xl border border-slate-200 bg-white sm:grid-cols-3">
          {Array.from({ length: 3 }, (_, index) => (
            <div
              key={index}
              className="flex gap-4 border-b border-slate-200 p-5 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0 lg:p-6"
            >
              <span className="size-11 shrink-0 rounded-full bg-slate-200" />
              <span className="min-w-0 flex-1 space-y-3">
                <span className="block h-4 w-2/3 rounded bg-slate-200" />
                <span className="block h-5 w-4/5 rounded bg-slate-200" />
                <span className="block h-3 w-1/2 rounded bg-slate-100" />
              </span>
            </div>
          ))}
        </div>
        <div className="grid gap-8 lg:grid-cols-3">
          <div className="h-72 rounded-xl border border-slate-200 bg-white lg:col-span-2" />
          <div className="h-72 rounded-xl border border-slate-200 bg-white" />
        </div>
      </div>
    </div>
  )
}
