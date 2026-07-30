import { useEffect, useRef, useState } from 'react'
import type { UserRole } from '@features/auth/types/auth'
import type { CoachResponse } from '../../types/coach'

interface CoachStatusToggleProps {
  coach: CoachResponse
  currentUserId: string
  currentUserRole: UserRole
  isUpdating: boolean
  onStatusChange: (isActive: boolean) => Promise<void> | void
}

export default function CoachStatusToggle({
  coach,
  currentUserId,
  currentUserRole,
  isUpdating,
  onStatusChange,
}: CoachStatusToggleProps) {
  const [isConfirming, setIsConfirming] = useState(false)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)
  const isSelf = coach.id === currentUserId

  useEffect(() => {
    if (isConfirming) cancelButtonRef.current?.focus()
  }, [isConfirming])

  if (currentUserRole !== 'head coach') return null

  if (isConfirming) {
    return (
      <div
        role="alertdialog"
        aria-labelledby="deactivate-coach-title"
        aria-describedby="deactivate-coach-description"
        className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-950"
      >
        <h3 id="deactivate-coach-title" className="text-base font-bold">
          Deactivate {coach.first_name} {coach.last_name}?
        </h3>
        <p
          id="deactivate-coach-description"
          className="mt-2 text-sm leading-6"
        >
          The coach will no longer be able to log in, and all active sessions
          will be revoked. Team assignments and historical data will be
          preserved, and the account can be reactivated later.
        </p>
        <div className="mt-4 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            ref={cancelButtonRef}
            type="button"
            disabled={isUpdating}
            className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-slate-400"
            onClick={() => setIsConfirming(false)}
          >
            Keep active
          </button>
          <button
            type="button"
            disabled={isUpdating}
            className="min-h-11 rounded-lg bg-red-800 px-4 text-sm font-semibold text-white hover:bg-red-900 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-red-300"
            onClick={() => {
              void Promise.resolve(onStatusChange(false)).then(() =>
                setIsConfirming(false),
              )
            }}
          >
            {isUpdating ? 'Deactivating…' : 'Confirm deactivation'}
          </button>
        </div>
      </div>
    )
  }

  const actionLabel = coach.is_active
    ? 'Deactivate coach'
    : isUpdating
      ? 'Reactivating…'
      : 'Reactivate coach'

  return (
    <section aria-labelledby="coach-account-status-title">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3
            id="coach-account-status-title"
            className="text-base font-bold text-slate-900"
          >
            Account access
          </h3>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            {coach.is_active
              ? 'Deactivate access while preserving academy records.'
              : 'Restore login access with a fresh authentication session.'}
          </p>
        </div>
        <button
          type="button"
          disabled={isSelf || isUpdating}
          className={`min-h-11 shrink-0 rounded-lg px-4 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:cursor-not-allowed ${
            coach.is_active
              ? 'border border-red-300 bg-white text-red-900 hover:bg-red-50 focus:ring-red-800 disabled:border-red-200 disabled:bg-red-50 disabled:text-red-950'
              : 'bg-slate-900 text-white hover:bg-slate-800 focus:ring-academy disabled:bg-slate-400'
          }`}
          onClick={() => {
            if (coach.is_active) setIsConfirming(true)
            else void onStatusChange(true)
          }}
        >
          {actionLabel}
        </button>
      </div>
      {isSelf ? (
        <p className="mt-2 text-sm font-medium text-slate-700">
          You cannot deactivate your own account.
        </p>
      ) : null}
      {isUpdating ? (
        <p role="status" className="sr-only">
          Updating coach status
        </p>
      ) : null}
    </section>
  )
}
