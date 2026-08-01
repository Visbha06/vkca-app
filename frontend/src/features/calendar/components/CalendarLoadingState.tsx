interface CalendarLoadingStateProps {
  label?: string
}

export default function CalendarLoadingState({
  label = 'Loading calendar',
}: CalendarLoadingStateProps) {
  return (
    <div
      role="status"
      aria-label={label}
      className="overflow-hidden rounded-lg border border-slate-200 bg-white"
    >
      <div className="grid grid-cols-7 border-b border-slate-200 bg-slate-50">
        {Array.from({ length: 7 }, (_, index) => (
          <div key={index} className="min-h-11 border-r border-slate-200" />
        ))}
      </div>
      <div className="grid grid-cols-7">
        {Array.from({ length: 42 }, (_, index) => (
          <div
            key={index}
            className="min-h-24 border-b border-r border-slate-200 bg-slate-50 p-2 last:border-r-0"
          >
            <div className="h-4 w-6 rounded bg-slate-200" />
            <div className="mt-4 h-3 w-3/4 rounded bg-slate-100" />
          </div>
        ))}
      </div>
    </div>
  )
}
