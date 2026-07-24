import type { PlayerResponse } from '../types/player'
import PlayerCard from './PlayerCard'

interface PlayerCardGridProps {
  players: PlayerResponse[]
  showSkeletons: boolean
  onSelect: (player: PlayerResponse) => void
  emptyMessage?: string
  emptyDescription?: string
  emptyActionLabel?: string
  emptyActionVariant?: 'primary' | 'secondary'
  onEmptyAction?: () => void
}

function PlayerCardSkeleton() {
  return (
    <div className="min-h-32 animate-pulse rounded-xl border border-slate-200 bg-white p-3 motion-reduce:animate-none">
      <div className="flex gap-3">
        <div className="size-11 shrink-0 rounded-full bg-slate-200" />
        <div className="min-w-0 flex-1">
          <div className="h-5 w-2/3 rounded bg-slate-200" />
          <div className="mt-2 h-4 w-1/2 rounded bg-slate-200" />
        </div>
      </div>
      <div className="mt-2 border-t border-slate-200 pt-2">
        <div className="h-5 w-4/5 rounded bg-slate-200" />
        <div className="mt-2 h-4 w-1/3 rounded bg-slate-200" />
      </div>
    </div>
  )
}

function LoadingGrid() {
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">Loading players</span>
      <div
        aria-hidden="true"
        className="grid grid-cols-1 justify-start gap-4 sm:grid-cols-[repeat(auto-fill,minmax(20rem,24rem))]"
      >
        {Array.from({ length: 6 }, (_, index) => (
          <PlayerCardSkeleton key={index} />
        ))}
      </div>
    </div>
  )
}

export default function PlayerCardGrid({
  players,
  showSkeletons,
  onSelect,
  emptyMessage = 'No players found.',
  emptyDescription = 'Player profiles will appear here when they are available.',
  emptyActionLabel,
  emptyActionVariant = 'primary',
  onEmptyAction,
}: PlayerCardGridProps) {
  if (showSkeletons) return <LoadingGrid />

  if (players.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white px-5 py-12 text-center sm:px-6">
        <p className="font-semibold text-slate-900">{emptyMessage}</p>
        <p className="mx-auto mt-2 max-w-prose text-sm leading-6 text-slate-600">
          {emptyDescription}
        </p>
        {emptyActionLabel !== undefined && onEmptyAction !== undefined ? (
          <button
            type="button"
            className={`mt-5 inline-flex min-h-11 items-center justify-center rounded-lg px-4 text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 ${
              emptyActionVariant === 'primary'
                ? 'bg-slate-900 text-white hover:bg-slate-800'
                : 'border border-academy bg-white text-slate-900 hover:bg-academy/10'
            }`}
            onClick={onEmptyAction}
          >
            {emptyActionLabel}
          </button>
        ) : null}
      </div>
    )
  }

  return (
    <ul
      aria-label="Players"
      className="grid grid-cols-1 justify-start gap-4 sm:grid-cols-[repeat(auto-fill,minmax(20rem,24rem))]"
    >
      {players.map((player) => (
        <li key={player.id} className="h-full">
          <PlayerCard player={player} onSelect={onSelect} />
        </li>
      ))}
    </ul>
  )
}
