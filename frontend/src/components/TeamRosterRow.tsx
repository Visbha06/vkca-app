import type { TeamRosterSelection } from '../types/team'
import type { DragEvent } from 'react'
import PlayerSearchDropdown from './PlayerSearchDropdown'

interface TeamRosterRowProps {
  index: number
  player: TeamRosterSelection | null
  selectedPlayerIds: string[]
  disabled?: boolean
  isDragging?: boolean
  isDropTarget?: boolean
  canMoveUp?: boolean
  canMoveDown?: boolean
  onChange: (player: TeamRosterSelection | null) => void
  onDragStart?: () => void
  onDragOver?: (event: DragEvent<HTMLLIElement>) => void
  onDrop?: (event: DragEvent<HTMLLIElement>) => void
  onDragEnd?: () => void
  onMoveUp?: () => void
  onMoveDown?: () => void
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
  isDragging = false,
  isDropTarget = false,
  canMoveUp = false,
  canMoveDown = false,
  onChange,
  onDragStart,
  onDragOver,
  onDrop,
  onDragEnd,
  onMoveUp,
  onMoveDown,
  onPlayerInfo,
}: TeamRosterRowProps) {
  const rowNumber = index + 1
  const isRequired = rowNumber <= 7
  const name = player === null ? null : fullName(player)

  return (
    <li
      className={`flex flex-col gap-2 border-b border-slate-200 py-3 last:border-b-0 sm:flex-row sm:items-center ${
        isDragging ? 'opacity-50' : ''
      } ${isDropTarget ? 'border-2 border-dashed border-academy px-2' : ''}`}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <div className="flex min-h-11 items-center gap-2 sm:w-28 sm:shrink-0">
        <span
          role="img"
          aria-label={
            name === null
              ? `Drag player ${rowNumber} to reorder`
              : `Drag ${name} to reorder`
          }
          draggable={!disabled && player !== null}
          className="flex size-11 cursor-grab items-center justify-center text-slate-500 active:cursor-grabbing"
          title={name === null ? 'Select a player before reordering' : 'Drag to reorder'}
          onDragStart={onDragStart}
          onDragEnd={onDragEnd}
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
            name === null ? `Move player ${rowNumber} up` : `Move ${name} up`
          }
          disabled={disabled || player === null || !canMoveUp}
          className="flex size-11 items-center justify-center rounded-lg text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-slate-400 disabled:hover:bg-transparent"
          onClick={onMoveUp}
        >
          <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 24 24">
            <path d="m7 14 5-5 5 5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
          </svg>
        </button>
        <button
          type="button"
          aria-label={
            name === null
              ? `Move player ${rowNumber} down`
              : `Move ${name} down`
          }
          disabled={disabled || player === null || !canMoveDown}
          className="flex size-11 items-center justify-center rounded-lg text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-slate-400 disabled:hover:bg-transparent"
          onClick={onMoveDown}
        >
          <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 24 24">
            <path d="m7 10 5 5 5-5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
          </svg>
        </button>
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
