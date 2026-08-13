interface DashboardErrorStateProps {
  message?: string
  onRetry: () => void
}

export default function DashboardErrorState({
  message = 'Unable to load your dashboard.',
  onRetry,
}: DashboardErrorStateProps) {
  return (
    <div
      role="alert"
      className="my-8 rounded-xl border border-red-200 bg-red-50 p-5 text-red-950 sm:p-6"
    >
      <h2 className="text-lg font-bold">Your briefing is unavailable</h2>
      <p className="mt-2 text-sm leading-6">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 min-h-11 rounded-lg border border-red-800 bg-white px-4 text-sm font-semibold hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2"
      >
        Retry dashboard
      </button>
    </div>
  )
}
