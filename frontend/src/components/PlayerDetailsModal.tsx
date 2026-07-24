import type { PlayerResponse } from '../types/player'
import {
  BATTING_STYLE_LABELS,
  BOWLING_STYLE_LABELS,
  formatEnum,
} from '../utils/enumLabels'
import { toDisplayDate } from '../utils/formatDate'
import ModalDialog from './ModalDialog'
import PlayerCricketSummary from './PlayerCricketSummary'
import PlayerIdentity from './PlayerIdentity'
import PlayerTypeBadge from './PlayerTypeBadge'

interface PlayerDetailsModalProps {
  player: PlayerResponse
  onClose: () => void
  onEdit?: () => void
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
  onEdit,
}: PlayerDetailsModalProps) {
  return (
    <ModalDialog
      labelledBy="player-details-title"
      onClose={onClose}
      testId="player-details-backdrop"
    >
      <div className="relative bg-white text-slate-900">
        <header className="border-b border-slate-200 px-5 py-4 pr-16 sm:px-6 sm:pr-16">
          <div>
            <PlayerIdentity
              avatarSize="modal"
              player={player}
              showAllTeams
              titleAs="h2"
              titleId="player-details-title"
            />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2">
            <PlayerTypeBadge playerType={player.player_type} />
            <p className="text-sm leading-5 text-slate-700">
              <PlayerCricketSummary player={player} />
            </p>
          </div>
        </header>

        <div className="px-5 py-4 sm:px-6">
          <section aria-labelledby="playing-profile-title">
            <h3
              id="playing-profile-title"
              className="text-base font-bold text-slate-900"
            >
              Playing profile
            </h3>
            <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2">
              <DetailItem
                label="Batting style"
                value={formatEnum(player.batting_style, BATTING_STYLE_LABELS)}
              />
              <DetailItem
                label="Bowling style"
                value={formatEnum(player.bowling_style, BOWLING_STYLE_LABELS)}
              />
              <DetailItem
                label="Date of birth"
                value={toDisplayDate(player.date_of_birth)}
              />
            </dl>
          </section>

          {player.bio?.trim() ? (
            <section
              aria-labelledby="player-biography-title"
              className="mt-5 border-t border-slate-200 pt-5"
            >
              <h3
                id="player-biography-title"
                className="text-base font-bold text-slate-900"
              >
                Biography
              </h3>
              <p className="mt-2 max-w-prose whitespace-pre-wrap text-base leading-6 text-slate-700">
                {player.bio}
              </p>
            </section>
          ) : null}

          {onEdit !== undefined ? (
            <div className="mt-5 flex justify-end border-t border-slate-200 pt-4">
              <button
                type="button"
                className="inline-flex min-h-11 items-center justify-center rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white transition-colors hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
                onClick={onEdit}
              >
                Edit Player
              </button>
            </div>
          ) : null}
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
    </ModalDialog>
  )
}
