import type { PlayerResponse } from '../types/player'
import PlayerCard from './PlayerCard'

interface PlayerCardGridProps {
  players: PlayerResponse[]
  isLoading: boolean
  onSelect: (player: PlayerResponse) => void
  emptyMessage?: string
}

function LoadingGrid() {
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">Loading players</span>
      <div
        aria-hidden="true"
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3"
      >
        {Array.from({ length: 6 }, (_, index) => (
          <div
            key={index}
            className="min-h-44 animate-pulse rounded-xl border border-slate-200 bg-white p-5 motion-reduce:animate-none sm:p-6"
          >
            <div className="h-6 w-2/3 rounded bg-slate-200" />
            <div className="mt-5 h-4 w-1/2 rounded bg-slate-200" />
            <div className="mt-10 h-4 w-1/3 rounded bg-slate-200" />
          </div>
        ))}
      </div>
    </div>
  )
}

export default function PlayerCardGrid({
  players,
  isLoading,
  onSelect,
  emptyMessage = 'No players found.',
}: PlayerCardGridProps) {
  if (isLoading) return <LoadingGrid />

  if (players.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white px-5 py-12 text-center sm:px-6">
        <p className="font-semibold text-slate-900">{emptyMessage}</p>
        <p className="mx-auto mt-2 max-w-prose text-sm leading-6 text-slate-600">
          Player profiles will appear here when they are available.
        </p>
      </div>
    )
  }

  return (
    <ul
      aria-label="Players"
      className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3"
    >
      {players.map((player) => (
        <li key={player.id}>
          <PlayerCard player={player} onSelect={onSelect} />
        </li>
      ))}
    </ul>
  )
}
