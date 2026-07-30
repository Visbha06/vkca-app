import type { CoachResponse } from '../../types/coach'
import CoachIdentity from '../coach-details/CoachIdentity'
import CoachRoleBadge from '../coach-details/CoachRoleBadge'
import CoachStatusIndicator from './CoachStatusIndicator'

interface CoachCardProps {
  coach: CoachResponse
  interactive?: boolean
  onSelect: (coach: CoachResponse) => void
}

export default function CoachCard({
  coach,
  interactive = true,
  onSelect,
}: CoachCardProps) {
  const fullName = `${coach.first_name} ${coach.last_name}`.trim()
  const visibleTeams = coach.teams.slice(0, 2)
  const additionalTeams = coach.teams.length - visibleTeams.length

  return (
    <button
      type="button"
      aria-label={`View ${fullName} details`}
      aria-disabled={interactive ? undefined : true}
      disabled={!interactive}
      tabIndex={interactive ? undefined : -1}
      className={`group flex h-full min-h-32 w-full flex-col rounded-xl border p-3 text-left transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 motion-reduce:transition-none ${
        coach.is_active
          ? 'border-slate-200 bg-white hover:border-academy hover:bg-academy/5'
          : 'border-slate-200 bg-slate-50 text-slate-600 hover:border-slate-300'
      }`}
      onClick={() => onSelect(coach)}
    >
      <CoachIdentity
        coach={coach}
        trailing={<span aria-hidden="true" className="text-slate-500 transition-transform duration-200 group-hover:translate-x-0.5 motion-reduce:transition-none">→</span>}
      />
      <span className="mt-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-t border-slate-200 pt-2">
        <CoachRoleBadge role={coach.role} />
        <CoachStatusIndicator isActive={coach.is_active} />
      </span>
      <span className="mt-auto pt-2 text-sm leading-5">
        <span className="font-medium text-slate-500">Teams:</span>{' '}
        <span className="text-slate-700">
          {visibleTeams.length === 0 ? (
            'No teams assigned'
          ) : (
            <>
              {visibleTeams.map((team) => team.name).join(', ')}
              {additionalTeams > 0 ? ` +${additionalTeams} more` : ''}
            </>
          )}
        </span>
      </span>
    </button>
  )
}
