import type { TeamResponse } from '@features/teams/types/team'
import TeamAssignmentList from './TeamAssignmentList'

interface TeamAssignmentsFormProps {
  coachName: string
  conflictMessage: string | null
  teams: TeamResponse[]
  selectedTeamIds: Set<string>
  errorMessage: string | null
  isDirty: boolean
  isHidden: boolean
  isLoading: boolean
  isReloading: boolean
  isSubmitting: boolean
  onCancel: () => void
  onRetry: () => void
  onReload: () => void
  onSubmit: () => void
  onToggle: (teamId: string) => void
}

export default function TeamAssignmentsForm({
  coachName,
  conflictMessage,
  teams,
  selectedTeamIds,
  errorMessage,
  isDirty,
  isHidden,
  isLoading,
  isReloading,
  isSubmitting,
  onCancel,
  onRetry,
  onReload,
  onSubmit,
  onToggle,
}: TeamAssignmentsFormProps) {
  return (
    <div
      hidden={isHidden}
      inert={isHidden ? true : undefined}
      className="relative bg-white text-slate-900"
    >
      <header className="border-b border-slate-200 p-5 pr-16 sm:p-6 sm:pr-16">
        <h2 id="team-assignments-title" className="text-xl font-bold">
          Edit team assignments
        </h2>
        <p className="mt-2 max-w-prose text-sm leading-6 text-slate-700">
          Choose every team assigned to {coachName}.
        </p>
      </header>
      <div className="max-h-96 overflow-y-auto p-5 sm:p-6">
        {conflictMessage !== null ? (
          <div
            role="alert"
            className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950"
          >
            <p className="font-semibold">{conflictMessage}</p>
            <button
              type="button"
              disabled={isReloading}
              className="mt-3 min-h-11 rounded-lg border border-amber-800 bg-white px-4 font-semibold hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-amber-500"
              onClick={onReload}
            >
              {isReloading ? 'Reloading…' : 'Reload'}
            </button>
          </div>
        ) : null}
        {errorMessage !== null ? (
          <div
            role="alert"
            className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm font-medium text-red-950"
          >
            {errorMessage}
            {!isLoading && teams.length === 0 ? (
              <button
                type="button"
                className="mt-3 block min-h-11 rounded-lg border border-red-800 bg-white px-4 font-semibold hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2"
                onClick={onRetry}
              >
                Retry
              </button>
            ) : null}
          </div>
        ) : null}
        {isLoading ? (
          <div role="status" className="space-y-3" aria-label="Loading teams">
            <span className="sr-only">Loading teams</span>
            {[0, 1, 2].map((item) => (
              <div
                key={item}
                className="h-14 animate-pulse rounded-lg bg-slate-100 motion-reduce:animate-none"
              />
            ))}
          </div>
        ) : errorMessage === null || teams.length > 0 ? (
          <TeamAssignmentList
            teams={teams}
            selectedTeamIds={selectedTeamIds}
            disabled={isSubmitting || isReloading || conflictMessage !== null}
            onToggle={onToggle}
          />
        ) : null}
      </div>
      <footer className="flex flex-col-reverse gap-3 border-t border-slate-200 p-5 sm:flex-row sm:justify-end sm:p-6">
        <button
          type="button"
          disabled={isSubmitting || isReloading}
          className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
          onClick={onCancel}
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={
            isSubmitting ||
            isReloading ||
            conflictMessage !== null ||
            isLoading ||
            !isDirty
          }
          className="min-h-11 rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-400"
          onClick={onSubmit}
        >
          {isSubmitting
            ? 'Saving assignments…'
            : isReloading
              ? 'Reloading assignments…'
              : 'Save assignments'}
        </button>
      </footer>
      <button
        type="button"
        aria-label="Close team assignments"
        data-modal-initial-focus
        disabled={isSubmitting || isReloading}
        className="absolute right-3 top-3 flex size-11 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-slate-400 sm:right-4 sm:top-4"
        onClick={onCancel}
      >
        <svg aria-hidden="true" className="size-6" fill="none" viewBox="0 0 24 24">
          <path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
        </svg>
      </button>
    </div>
  )
}
