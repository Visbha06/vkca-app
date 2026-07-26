import type { PlayerResponse } from '../../types/player'
import { toDisplayDate } from '@shared/utils/formatDate'
import PlayerCricketSummary from '../player-details/PlayerCricketSummary'
import PlayerIdentity from '../player-details/PlayerIdentity'
import PlayerTypeBadge from '../player-details/PlayerTypeBadge'

interface PlayerCardProps {
  player: PlayerResponse
  onSelect: (player: PlayerResponse) => void
}

export default function PlayerCard({ player, onSelect }: PlayerCardProps) {
  const fullName = `${player.first_name} ${player.last_name}`.trim()

  return (
    <button
      type="button"
      aria-label={`View ${fullName} details`}
      className="group flex h-full min-h-32 w-full flex-col items-stretch rounded-xl border border-slate-200 bg-white p-3 text-left transition-colors duration-200 hover:border-academy hover:bg-academy/5 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 motion-reduce:transition-none"
      onClick={() => onSelect(player)}
    >
      <PlayerIdentity
        player={player}
        trailing={
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
        }
      />
      <span className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-slate-200 pt-2">
        <PlayerTypeBadge playerType={player.player_type} />
        <span className="min-w-0 flex-1 text-sm leading-5 text-slate-700">
          <PlayerCricketSummary compact player={player} />
        </span>
      </span>
      <span className="mt-auto pt-2 text-sm leading-5 text-slate-600">
        Born {toDisplayDate(player.date_of_birth)}
      </span>
    </button>
  )
}
