import { useEffect, useRef, type ReactNode } from 'react'

interface PlayerFormFeedbackProps {
  action?: ReactNode
  message: string | null
}

export default function PlayerFormFeedback({
  action,
  message,
}: PlayerFormFeedbackProps) {
  const alertRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (message !== null) alertRef.current?.focus()
  }, [message])

  if (message === null) return null

  return (
    <div
      ref={alertRef}
      role="alert"
      tabIndex={-1}
      className="mb-5 rounded-lg border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-950 focus:outline-none"
    >
      <p>{message}</p>
      {action}
    </div>
  )
}
