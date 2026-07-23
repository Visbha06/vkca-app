import { useCallback, useRef, useState, type MouseEvent } from 'react'
import { ApiClientError } from '../api/client'
import { createPlayer } from '../api/playerApi'
import type { PlayerCreatePayload, PlayerResponse } from '../types/player'
import PlayerForm, { type PlayerFormHandle } from './PlayerForm'
import { useModalDialog } from './useModalDialog'

interface AddPlayerModalProps {
  onClose: () => void
  onCreated: (player: PlayerResponse) => void
}

export default function AddPlayerModal({
  onClose,
  onCreated,
}: AddPlayerModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const formRef = useRef<PlayerFormHandle>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const requestClose = useCallback(() => {
    if (formRef.current !== null) return formRef.current.requestClose()
    onClose()
    return true
  }, [onClose])
  useModalDialog(dialogRef, requestClose)

  function handleBackdropClick(event: MouseEvent<HTMLDivElement>) {
    if (event.target === event.currentTarget) requestClose()
  }

  async function handleSubmit(payload: PlayerCreatePayload) {
    if (isSubmitting) return
    setIsSubmitting(true)
    setErrorMessage(null)
    try {
      const player = await createPlayer(payload)
      setIsSubmitting(false)
      onCreated(player)
      onClose()
    } catch (error) {
      setErrorMessage(
        error instanceof ApiClientError && error.status === 403
          ? 'You do not have permission to add players.'
          : 'Unable to create player. Please try again.',
      )
      setIsSubmitting(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-hidden bg-slate-900/60 p-3 sm:p-6"
      data-testid="add-player-backdrop"
      onClick={handleBackdropClick}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-player-title"
        aria-describedby="add-player-description"
        className="relative max-h-full w-full max-w-3xl overflow-y-auto overscroll-contain rounded-xl border border-slate-200 bg-white text-slate-900"
      >
        <header className="border-b border-slate-200 p-5 pr-16 sm:p-6 sm:pr-16">
          <h2 id="add-player-title" className="text-2xl font-bold tracking-tight">
            Add player
          </h2>
          <p id="add-player-description" className="mt-2 max-w-prose text-sm leading-6 text-slate-600">
            Create an active player profile. Required fields are marked by validation when missing.
          </p>
        </header>

        <PlayerForm
          ref={formRef}
          onSubmit={handleSubmit}
          onCancel={onClose}
          isSubmitting={isSubmitting}
          errorMessage={errorMessage}
          onChange={() => setErrorMessage(null)}
        />

        <button
          type="button"
          aria-label="Close Add Player"
          disabled={isSubmitting}
          className="absolute right-3 top-3 flex size-11 items-center justify-center rounded-lg text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-slate-400 sm:right-4 sm:top-4"
          onClick={requestClose}
        >
          <svg aria-hidden="true" className="size-6" fill="none" viewBox="0 0 24 24">
            <path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
          </svg>
        </button>
      </div>
    </div>
  )
}
