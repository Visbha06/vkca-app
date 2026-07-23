import { useRef, type MouseEvent } from 'react'
import type { PlayerResponse } from '../types/player'
import {
  BATTING_STYLE_LABELS,
  BOWLING_STYLE_LABELS,
  PLAYER_TYPE_LABELS,
  formatEnum,
} from '../utils/enumLabels'
import { toDisplayDate } from '../utils/formatDate'
import PlayerInformationSection from './PlayerInformationSection'
import { useModalDialog } from './useModalDialog'

interface PlayerDetailsModalProps {
  player: PlayerResponse
  onClose: () => void
}

interface DetailItemProps {
  label: string
  value: string
}

function DetailItem({ label, value }: DetailItemProps) {
  return (
    <div>
      <dt className="text-sm font-semibold text-slate-600">{label}</dt>
      <dd className="mt-1 text-base font-medium text-slate-900">{value}</dd>
    </div>
  )
}

export default function PlayerDetailsModal({
  player,
  onClose,
}: PlayerDetailsModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  useModalDialog(dialogRef, onClose)

  const fullName = `${player.first_name} ${player.last_name}`
  const teamNames = player.teams.map((team) => team.name).join(', ')

  function handleBackdropClick(event: MouseEvent<HTMLDivElement>) {
    if (event.target === event.currentTarget) onClose()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-hidden bg-slate-900/60 p-3 sm:p-6"
      data-testid="player-details-backdrop"
      onClick={handleBackdropClick}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="player-details-title"
        aria-describedby="player-details-description"
        className="relative max-h-full w-full max-w-2xl overflow-y-auto overscroll-contain rounded-xl border border-slate-200 bg-white text-slate-900"
      >
        <header className="border-b border-slate-200 p-5 pr-16 sm:p-6 sm:pr-16">
          <p className="text-sm font-semibold text-slate-600">Player details</p>
          <h2 id="player-details-title" className="mt-1 text-2xl font-bold tracking-tight">
            {fullName}
          </h2>
          <p id="player-details-description" className="mt-2 text-sm leading-6 text-slate-600">
            Identity, playing style, and current team membership.
          </p>
        </header>

        <div className="p-5 sm:p-6">
          <dl className="grid grid-cols-1 gap-x-6 gap-y-5 sm:grid-cols-2">
            <DetailItem label="Date of birth" value={toDisplayDate(player.date_of_birth)} />
            <DetailItem
              label="Player type"
              value={formatEnum(player.player_type, PLAYER_TYPE_LABELS)}
            />
            <DetailItem
              label="Batting style"
              value={formatEnum(player.batting_style, BATTING_STYLE_LABELS)}
            />
            <DetailItem
              label="Bowling style"
              value={formatEnum(player.bowling_style, BOWLING_STYLE_LABELS)}
            />
            <div className="sm:col-span-2">
              <DetailItem label="Teams" value={teamNames || 'Unassigned'} />
            </div>
          </dl>

          <PlayerInformationSection
            bio={player.bio}
            metadata={player.player_metadata}
          />

          <section
            aria-labelledby="player-statistics-title"
            className="mt-6 border-t border-slate-200 pt-6"
          >
            <h3 id="player-statistics-title" className="font-bold text-slate-900">
              Player statistics
            </h3>
            <p className="mt-2 max-w-prose text-sm leading-6 text-slate-600">
              Player statistics deferred to a future specification.
            </p>
          </section>
        </div>

        <button
          type="button"
          aria-label="Close player details"
          data-modal-initial-focus
          className="absolute right-3 top-3 flex size-11 items-center justify-center rounded-lg text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 sm:right-4 sm:top-4"
          onClick={onClose}
        >
          <svg aria-hidden="true" className="size-6" fill="none" viewBox="0 0 24 24">
            <path
              d="m6 6 12 12M18 6 6 18"
              stroke="currentColor"
              strokeLinecap="round"
              strokeWidth="2"
            />
          </svg>
        </button>
      </div>
    </div>
  )
}
