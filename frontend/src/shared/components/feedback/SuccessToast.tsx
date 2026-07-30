import { useEffect } from 'react'

const DEFAULT_DISMISS_DELAY = 4500

interface SuccessToastProps {
  message: string
  onDismiss: () => void
  dismissDelay?: number
}

export default function SuccessToast({
  message,
  onDismiss,
  dismissDelay = DEFAULT_DISMISS_DELAY,
}: SuccessToastProps) {
  useEffect(() => {
    const timeoutId = window.setTimeout(onDismiss, dismissDelay)
    return () => window.clearTimeout(timeoutId)
  }, [dismissDelay, message, onDismiss])

  return (
    <div className="pointer-events-none fixed right-4 top-4 z-toast flex max-w-[calc(100vw-2rem)] justify-end sm:right-6 sm:top-6">
      <div
        role="status"
        aria-atomic="true"
        className="pointer-events-auto flex w-full max-w-sm items-center gap-3 rounded-lg bg-slate-900 px-4 py-2.5 text-sm text-white"
      >
        <span
          aria-hidden="true"
          className="size-2.5 shrink-0 rounded-full bg-emerald-400"
        />
        <span className="min-w-0 flex-1 font-medium leading-5">
          {message}
        </span>
        <button
          type="button"
          className="min-h-11 shrink-0 rounded-md px-2 font-semibold text-slate-200 underline decoration-slate-500 underline-offset-4 hover:text-white focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 focus:ring-offset-slate-900"
          onClick={onDismiss}
        >
          Dismiss
        </button>
      </div>
    </div>
  )
}
