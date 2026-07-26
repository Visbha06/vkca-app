import type { TeamResponse } from '../../types/team'
import { toDisplayDate } from '@shared/utils/formatDate'

const MAX_ROSTER_SIZE = 15

interface TeamRowProps {
  team: TeamResponse
  onSelect: (team: TeamResponse) => void
}

function updatedDate(timestamp: string) {
  return toDisplayDate(timestamp.slice(0, 10))
}

export default function TeamRow({ team, onSelect }: TeamRowProps) {
  const playerCount = Math.max(0, team.player_count)
  const remainingSpaces = Math.max(0, MAX_ROSTER_SIZE - playerCount)
  const occupancy = Math.min(100, (playerCount / MAX_ROSTER_SIZE) * 100)
  const ageGroup = team.age_group
  const capacityCopy =
    remainingSpaces === 0
      ? 'Roster full'
      : `${remainingSpaces} ${remainingSpaces === 1 ? 'place' : 'places'} available`

  return (
    <button
      type="button"
      aria-label={`View ${team.name}`}
      className="group grid min-h-20 w-full grid-cols-[2.75rem_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-3 px-4 py-4 text-left transition-colors duration-200 hover:bg-academy/5 focus:relative focus:z-10 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-academy active:bg-academy/10 sm:px-5 lg:grid-cols-[2.75rem_minmax(0,1.5fr)_minmax(7rem,1fr)_minmax(7rem,0.9fr)_minmax(6.5rem,0.8fr)_1.25rem] lg:gap-x-4 motion-reduce:transition-none"
      onClick={() => onSelect(team)}
    >
      <span
        aria-hidden="true"
        className={`col-start-1 row-start-1 flex size-11 shrink-0 items-center justify-center rounded-full bg-academy/20 font-bold text-slate-900 ${
          ageGroup.length > 4 ? 'text-[10px]' : 'text-sm'
        }`}
      >
        {ageGroup}
      </span>

      <span className="col-start-2 row-start-1 min-w-0">
        <span className="block break-words text-base font-bold leading-5 text-slate-900">
          {team.name}
        </span>
      </span>

      <svg
        aria-hidden="true"
        className="col-start-3 row-start-1 size-5 shrink-0 text-slate-500 transition-[color,transform] duration-200 group-hover:translate-x-0.5 group-hover:text-slate-800 motion-reduce:transition-none lg:col-start-6"
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

      <span className="col-span-2 col-start-2 row-start-2 min-w-0 lg:col-span-1 lg:col-start-3 lg:row-start-1">
        <span className="block text-sm font-semibold text-slate-800">
          {playerCount} of {MAX_ROSTER_SIZE} players
        </span>
        <span
          aria-hidden="true"
          className="mt-2 block h-1.5 w-full max-w-56 overflow-hidden rounded-full bg-slate-200"
        >
          <span
            className="block h-full rounded-full bg-academy"
            style={{ width: `${occupancy}%` }}
          />
        </span>
      </span>

      <span className="col-span-2 col-start-2 row-start-3 text-sm font-medium text-slate-700 lg:col-span-1 lg:col-start-4 lg:row-start-1">
        {capacityCopy}
      </span>

      <span className="col-span-2 col-start-2 row-start-4 text-sm text-slate-600 lg:col-span-1 lg:col-start-5 lg:row-start-1">
        <span className="lg:sr-only">Updated </span>
        {updatedDate(team.updated_at)}
      </span>
    </button>
  )
}
