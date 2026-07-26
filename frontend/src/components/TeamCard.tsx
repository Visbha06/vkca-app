import type { TeamResponse } from '../types/team'
import AgeGroupBadge from './AgeGroupBadge'

interface TeamCardProps {
  team: TeamResponse
  onSelect: (team: TeamResponse) => void
}

export default function TeamCard({ team, onSelect }: TeamCardProps) {
  const playerLabel = team.player_count === 1 ? 'player' : 'players'

  return (
    <button
      type="button"
      className="group flex min-h-36 w-full flex-col rounded-xl border border-slate-200 bg-white p-4 text-left transition-colors duration-200 hover:border-academy hover:bg-academy/5 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 motion-reduce:transition-none"
      aria-label={`View ${team.name}`}
      onClick={() => onSelect(team)}
    >
      <span className="flex items-start justify-between gap-3">
        <span className="min-w-0 text-base font-bold leading-6 text-slate-900">
          {team.name}
        </span>
        <svg
          aria-hidden="true"
          className="mt-0.5 size-5 shrink-0 text-slate-500 transition-[color,transform] duration-200 group-hover:translate-x-0.5 group-hover:text-slate-800 motion-reduce:transition-none"
          fill="none"
          viewBox="0 0 24 24"
        >
          <path
            d="m9 18 6-6-6-6"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
          />
        </svg>
      </span>
      <span className="mt-3">
        <AgeGroupBadge ageGroup={team.age_group} />
      </span>
      <span className="mt-auto border-t border-slate-200 pt-3 text-sm font-medium text-slate-700">
        {team.player_count} / 15 {playerLabel}
      </span>
    </button>
  )
}
