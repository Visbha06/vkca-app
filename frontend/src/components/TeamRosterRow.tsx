import type { TeamRosterSelection } from '../types/team'
import PlayerSearchDropdown from './PlayerSearchDropdown'

interface TeamRosterRowProps {
  index: number
  player: TeamRosterSelection | null
  selectedPlayerIds: string[]
  disabled?: boolean
  onChange: (player: TeamRosterSelection | null) => void
  onPlayerInfo: (player: TeamRosterSelection) => void
}

function fullName(player: TeamRosterSelection) {
  return `${player.first_name} ${player.last_name}`
}

export default function TeamRosterRow({
  index,
  player,
  selectedPlayerIds,
  disabled = false,
  onChange,
  onPlayerInfo,
}: TeamRosterRowProps) {
  const rowNumber = index + 1
  const isRequired = rowNumber <= 7
  const name = player === null ? null : fullName(player)

  return (
    <li className="flex flex-col gap-2 border-b border-slate-200 py-3 last:border-b-0 sm:flex-row sm:items-center">
      <div className="flex min-h-11 items-center gap-2 sm:w-28 sm:shrink-0">
        <span
          aria-hidden="true"
          className="flex size-11 items-center justify-center text-slate-500"
          title="Roster position"
        >
          <svg className="size-5" fill="currentColor" viewBox="0 0 20 20">
            <circle cx="6" cy="5" r="1.5" />
            <circle cx="14" cy="5" r="1.5" />
            <circle cx="6" cy="10" r="1.5" />
            <circle cx="14" cy="10" r="1.5" />
            <circle cx="6" cy="15" r="1.5" />
            <circle cx="14" cy="15" r="1.5" />
          </svg>
        </span>
        <span className="text-sm font-semibold text-slate-800">
          {rowNumber}
          <span className="ml-1 font-normal text-slate-600">
            {isRequired ? 'Required' : 'Optional'}
          </span>
        </span>
      </div>

      <div className="min-w-0 flex-1">
        <label className="sr-only" htmlFor={`team-player-${rowNumber}`}>
          Player {rowNumber} {isRequired ? '(required)' : '(optional)'}
        </label>
        <PlayerSearchDropdown
          key={player?.player_id ?? 'empty'}
          id={`team-player-${rowNumber}`}
          label={`Player ${rowNumber} ${isRequired ? '(required)' : '(optional)'}`}
          player={player}
          excludedPlayerIds={selectedPlayerIds}
          disabled={disabled}
          onChange={onChange}
        />
        {player !== null && !player.is_active ? (
          <p className="mt-2 text-sm font-medium text-red-800">
            Inactive player — replace before saving.
          </p>
        ) : null}
      </div>

      <div className="flex items-center justify-end gap-1 sm:shrink-0">
        <button
          type="button"
          aria-label={
            name === null
              ? `View player ${rowNumber} details`
              : `View ${name}`
          }
          disabled={disabled || player === null}
          className="flex size-11 items-center justify-center rounded-lg text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-slate-400 disabled:hover:bg-transparent"
          onClick={() => {
            if (player !== null) onPlayerInfo(player)
          }}
        >
          <svg
            aria-hidden="true"
            className="size-5"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" />
            <path d="M12 11v6M12 7.5v.5" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
          </svg>
        </button>
        <button
          type="button"
          aria-label={
            name === null ? `Remove player ${rowNumber}` : `Remove ${name}`
          }
          disabled={disabled || player === null}
          className="flex size-11 items-center justify-center rounded-lg text-red-800 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-red-400 disabled:hover:bg-transparent"
          onClick={() => onChange(null)}
        >
          <svg
            aria-hidden="true"
            className="size-5"
            fill="none"
            viewBox="0 0 24 24"
          >
            <path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v5M14 11v5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
          </svg>
        </button>
      </div>
    </li>
  )
}
