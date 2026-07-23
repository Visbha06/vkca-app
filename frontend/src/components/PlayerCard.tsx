import type { PlayerResponse } from '../types/player'
import { toDisplayDate } from '../utils/formatDate'

interface PlayerCardProps {
  player: PlayerResponse
  onSelect: (player: PlayerResponse) => void
}

export default function PlayerCard({ player, onSelect }: PlayerCardProps) {
  const fullName = `${player.first_name} ${player.last_name}`
  const teamNames = player.teams.map((team) => team.name).join(', ')

  return (
    <button
      type="button"
      aria-label={`View ${fullName} details`}
      className="group flex min-h-44 w-full flex-col items-start rounded-xl border border-slate-200 bg-white p-5 text-left transition-colors hover:border-academy hover:bg-academy/5 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 sm:p-6"
      onClick={() => onSelect(player)}
    >
      <span className="flex w-full items-start justify-between gap-4">
        <span className="min-w-0 text-xl font-bold text-slate-900 group-hover:text-slate-950">
          {fullName}
        </span>
        <svg
          aria-hidden="true"
          className="mt-1 size-5 shrink-0 text-academy transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none"
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
      <span className="mt-4 text-sm font-semibold text-slate-700">
        {teamNames || 'Unassigned'}
      </span>
      <span className="mt-auto pt-5 text-sm text-slate-600">
        Born {toDisplayDate(player.date_of_birth)}
      </span>
    </button>
  )
}
