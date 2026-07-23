import {
  useCallback,
  useRef,
  useState,
  type MouseEvent,
} from 'react'
import { ApiClientError } from '../api/client'
import { fetchPlayer, updatePlayer } from '../api/playerApi'
import type {
  PlayerCreatePayload,
  PlayerResponse,
  PlayerUpdatePayload,
} from '../types/player'
import PlayerForm, { type PlayerFormHandle } from './PlayerForm'
import { useModalDialog } from './useModalDialog'

interface EditPlayerModalProps {
  player: PlayerResponse
  onClose: () => void
  onUpdated: (player: PlayerResponse) => void
}

const conflictMessage =
  'This player was updated by another user. Reload the latest data before trying again.'

export default function EditPlayerModal({
  player,
  onClose,
  onUpdated,
}: EditPlayerModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const formRef = useRef<PlayerFormHandle>(null)
  const [currentPlayer, setCurrentPlayer] = useState(player)
  const [formRevision, setFormRevision] = useState(0)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isReloading, setIsReloading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [hasConflict, setHasConflict] = useState(false)
  const requestClose = useCallback(() => {
    if (formRef.current !== null) return formRef.current.requestClose()
    onClose()
    return true
  }, [onClose])
  useModalDialog(dialogRef, requestClose)

  const fullName = `${currentPlayer.first_name} ${currentPlayer.last_name}`

  function handleBackdropClick(event: MouseEvent<HTMLDivElement>) {
    if (event.target === event.currentTarget) requestClose()
  }

  async function handleSubmit(payload: PlayerCreatePayload) {
    if (isSubmitting || isReloading) return
    setIsSubmitting(true)
    setErrorMessage(null)
    setHasConflict(false)

    const updatePayload: PlayerUpdatePayload = {
      ...payload,
      version_number: currentPlayer.version_number,
    }

    try {
      const updatedPlayer = await updatePlayer(currentPlayer.id, updatePayload)
      setIsSubmitting(false)
      onUpdated(updatedPlayer)
      onClose()
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 409) {
        setHasConflict(true)
        setErrorMessage(conflictMessage)
      } else {
        setErrorMessage(
          error instanceof ApiClientError && error.status === 403
            ? 'You do not have permission to edit players.'
            : 'Unable to update player. Please try again.',
        )
      }
      setIsSubmitting(false)
    }
  }

  async function handleReload() {
    if (isReloading) return
    setIsReloading(true)

    try {
      const latestPlayer = await fetchPlayer(currentPlayer.id)
      setCurrentPlayer(latestPlayer)
      setFormRevision((revision) => revision + 1)
      setErrorMessage(null)
      setHasConflict(false)
    } catch {
      setErrorMessage('Unable to reload the latest player. Please try again.')
      setHasConflict(true)
    } finally {
      setIsReloading(false)
    }
  }

  const reloadAction = hasConflict ? (
    <button
      type="button"
      disabled={isReloading}
      className="mt-3 inline-flex min-h-11 items-center justify-center rounded-lg border border-red-800 bg-white px-4 text-sm font-semibold text-red-950 transition-colors hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-red-400"
      onClick={handleReload}
    >
      {isReloading ? 'Reloading player…' : 'Reload latest player'}
    </button>
  ) : undefined

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-hidden bg-slate-900/60 p-3 sm:p-6"
      data-testid="edit-player-backdrop"
      onClick={handleBackdropClick}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-player-title"
        aria-describedby="edit-player-description"
        className="relative max-h-full w-full max-w-3xl overflow-y-auto overscroll-contain rounded-xl border border-slate-200 bg-white text-slate-900"
      >
        <header className="border-b border-slate-200 p-5 pr-16 sm:p-6 sm:pr-16">
          <h2
            id="edit-player-title"
            className="text-2xl font-bold tracking-tight"
          >
            Edit {fullName}
          </h2>
          <p
            id="edit-player-description"
            className="mt-2 max-w-prose text-sm leading-6 text-slate-600"
          >
            Update this player profile. Changes use the latest saved version.
          </p>
        </header>

        <PlayerForm
          key={`${currentPlayer.id}-${currentPlayer.version_number}-${formRevision}`}
          ref={formRef}
          player={currentPlayer}
          onSubmit={handleSubmit}
          onCancel={onClose}
          isSubmitting={isSubmitting || isReloading}
          errorMessage={errorMessage}
          errorAction={reloadAction}
          onChange={() => {
            if (!hasConflict) setErrorMessage(null)
          }}
        />

        <button
          type="button"
          aria-label="Close Edit Player"
          disabled={isSubmitting || isReloading}
          className="absolute right-3 top-3 flex size-11 items-center justify-center rounded-lg text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-slate-400 sm:right-4 sm:top-4"
          onClick={requestClose}
        >
          <svg
            aria-hidden="true"
            className="size-6"
            fill="none"
            viewBox="0 0 24 24"
          >
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
