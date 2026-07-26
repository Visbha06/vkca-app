import EmptyState from '@shared/components/feedback/EmptyState'
import type { PlayerResponse } from '../../types/player'
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
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3"
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
      <EmptyState
        title={emptyMessage}
        description={emptyDescription}
        action={
          emptyActionLabel !== undefined && onEmptyAction !== undefined
            ? {
                label: emptyActionLabel,
                onClick: onEmptyAction,
                variant: emptyActionVariant,
              }
            : undefined
        }
      />
    )
  }

  return (
    <ul
      aria-label="Players"
      className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3"
    >
      {players.map((player) => (
        <li key={player.id} className="h-full">
          <PlayerCard player={player} onSelect={onSelect} />
        </li>
      ))}
    </ul>
  )
}
