import type { UserRole } from '@features/auth/types/auth'
import ModalDialog from '@shared/components/overlays/ModalDialog'
import type { CoachResponse } from '../../types/coach'
import CoachIdentity from './CoachIdentity'
import CoachRoleBadge from './CoachRoleBadge'

const AVAILABILITY = 'Not available'
const NOTES_MADE = '0'

interface CoachDetailsModalProps {
  coach: CoachResponse
  currentUserRole: UserRole
  onClose: () => void
}

export default function CoachDetailsModal({
  coach,
  currentUserRole,
  onClose,
}: CoachDetailsModalProps) {
  const status = coach.is_active ? 'Active' : 'Inactive'
  const canManage = currentUserRole === 'head coach'

  return (
    <ModalDialog
      labelledBy="coach-details-title"
      onClose={onClose}
      testId="coach-details-backdrop"
    >
      <div className="relative bg-white text-slate-900">
        <header className="border-b border-slate-200 px-5 py-4 pr-16 sm:px-6 sm:pr-16">
          <CoachIdentity coach={coach} />
          <h2 id="coach-details-title" className="sr-only">
            {coach.first_name} {coach.last_name}
          </h2>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <CoachRoleBadge role={coach.role} />
            <span
              className={`text-sm font-semibold ${
                coach.is_active ? 'text-emerald-800' : 'text-slate-600'
              }`}
            >
              {status}
            </span>
          </div>
        </header>

        <div className="px-5 py-4 sm:px-6">
          <section aria-labelledby="coach-teams-title">
            <h3 id="coach-teams-title" className="text-base font-bold text-slate-900">
              Assigned teams
            </h3>
            {coach.teams.length === 0 ? (
              <p className="mt-2 text-base text-slate-600">No teams assigned</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {coach.teams.map((team) => (
                  <li key={team.id} className="text-base text-slate-700">
                    {team.name}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section
            aria-labelledby="coach-statistics-title"
            className="mt-5 border-t border-slate-200 pt-5"
          >
            <h3 id="coach-statistics-title" className="text-base font-bold text-slate-900">
              Statistics
            </h3>
            <dl className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-sm font-semibold text-slate-600">
                  Availability for next practice
                </dt>
                <dd className="mt-1 text-base font-medium text-slate-900">
                  {AVAILABILITY}
                </dd>
              </div>
              <div>
                <dt className="text-sm font-semibold text-slate-600">Notes made</dt>
                <dd className="mt-1 text-base font-medium text-slate-900">
                  {NOTES_MADE}
                </dd>
              </div>
            </dl>
          </section>

          {canManage ? (
            <p className="mt-5 border-t border-slate-200 pt-4 text-sm text-slate-600">
              Head Coach controls will appear here when account management is enabled.
            </p>
          ) : null}
        </div>

        <button
          type="button"
          aria-label="Close coach details"
          data-modal-initial-focus
          className="absolute right-3 top-3 flex size-11 items-center justify-center rounded-lg text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 sm:right-4 sm:top-4"
          onClick={onClose}
        >
          <svg aria-hidden="true" className="size-6" fill="none" viewBox="0 0 24 24">
            <path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
          </svg>
        </button>
      </div>
    </ModalDialog>
  )
}
