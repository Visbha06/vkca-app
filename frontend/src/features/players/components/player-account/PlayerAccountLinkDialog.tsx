import { useCallback, useRef, useState } from 'react'
import ModalDialog from '@shared/components/overlays/ModalDialog'
import type {
  PlayerAccountAssociationResponse,
  PlayerAccountSnapshot,
} from '../../types/player'
import PlayerAccountDialogContent from './PlayerAccountDialogContent'
import usePlayerAccountDialog, {
  type PlayerAccountDialogMode,
} from './usePlayerAccountDialog'

interface PlayerAccountLinkDialogProps {
  mode: PlayerAccountDialogMode
  playerId: string
  versionNumber: number
  currentAccount: PlayerAccountSnapshot | null
  onClose: () => void
  onConflict: () => void
  onSaved: (association: PlayerAccountAssociationResponse) => void
}

export default function PlayerAccountLinkDialog({
  mode,
  playerId,
  versionNumber,
  currentAccount,
  onClose,
  onConflict,
  onSaved,
}: PlayerAccountLinkDialogProps) {
  const [showDiscardConfirmation, setShowDiscardConfirmation] = useState(false)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const dialog = usePlayerAccountDialog({
    mode,
    playerId,
    versionNumber,
    currentAccount,
    onSaved,
  })
  const requestClose = useCallback(() => {
    if (dialog.isDirty) {
      setShowDiscardConfirmation(true)
      return
    }
    onClose()
  }, [dialog.isDirty, onClose])

  function continueEditing() {
    setShowDiscardConfirmation(false)
    requestAnimationFrame(() => closeButtonRef.current?.focus())
  }

  return (
    <ModalDialog
      labelledBy={showDiscardConfirmation ? 'player-account-unsaved-title' : 'player-account-dialog-title'}
      describedBy={showDiscardConfirmation ? 'player-account-unsaved-description' : 'player-account-dialog-description'}
      onClose={requestClose}
      testId="player-account-dialog"
    >
      {showDiscardConfirmation ? (
        <div className="p-5 text-slate-900 sm:p-6">
          <h2 id="player-account-unsaved-title" className="text-xl font-bold">Discard unsaved changes?</h2>
          <p id="player-account-unsaved-description" className="mt-2 max-w-prose text-sm leading-6 text-slate-700">Discarding clears your account search and selection without changing any Player account link.</p>
          <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <button type="button" data-modal-initial-focus onClick={continueEditing} className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2">Continue editing</button>
            <button type="button" onClick={onClose} className="min-h-11 rounded-lg bg-red-800 px-4 text-sm font-semibold text-white hover:bg-red-900 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2">Discard changes</button>
          </div>
        </div>
      ) : (
        <>
          <PlayerAccountDialogContent
            {...dialog}
            mode={mode}
            onCancel={requestClose}
            onConflict={onConflict}
            onSearch={dialog.searchAccounts}
            onSearchChange={dialog.setSearch}
            onSelect={dialog.setSelectedId}
            onSubmit={() => void dialog.submit()}
          />
          <button ref={closeButtonRef} type="button" aria-label="Close account linking" data-modal-initial-focus disabled={dialog.isSubmitting} onClick={requestClose} className="absolute right-3 top-3 flex size-11 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 sm:right-4 sm:top-4">
            <span aria-hidden="true" className="text-2xl leading-none">×</span>
          </button>
        </>
      )}
    </ModalDialog>
  )
}
