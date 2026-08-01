interface CalendarErrorStateProps {
  message?: string
  onRetry: () => void
}

export default function CalendarErrorState({
  message = 'Unable to load the calendar. Please try again.',
  onRetry,
}: CalendarErrorStateProps) {
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-950">
      <p className="font-semibold">{message}</p>
      <button
        type="button"
        className="mt-4 min-h-11 rounded-lg border border-red-800 px-4 text-sm font-semibold hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2"
        onClick={onRetry}
      >
        Retry
      </button>
    </div>
  )
}
