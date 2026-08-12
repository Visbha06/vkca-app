import { useCallback, useEffect, useState } from 'react'
import { fetchPlayerAccountAssociation } from '../../api/playerApi'
import type { PlayerAccountAssociationResponse } from '../../types/player'
import PlayerAccountLinkDialog from './PlayerAccountLinkDialog'
import type { PlayerAccountDialogMode } from './usePlayerAccountDialog'

interface PlayerAccountSectionProps {
  canManage: boolean
  playerId: string
  versionNumber: number
  onAssociationChanged: (association: PlayerAccountAssociationResponse) => void
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError'
}

export default function PlayerAccountSection({
  canManage,
  playerId,
  versionNumber,
  onAssociationChanged,
}: PlayerAccountSectionProps) {
  const [association, setAssociation] =
    useState<PlayerAccountAssociationResponse | null>(null)
  const [dialogMode, setDialogMode] =
    useState<PlayerAccountDialogMode | null>(null)
  const [requestState, setRequestState] = useState<'loading' | 'ready' | 'error'>(
    'loading',
  )
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    if (!canManage) return
    const controller = new AbortController()
    void fetchPlayerAccountAssociation(playerId, controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) {
          setAssociation(response)
          setRequestState('ready')
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && !isAbortError(error)) {
          setErrorMessage('Unable to load the linked account. Please try again.')
          setRequestState('error')
        }
      })
    return () => controller.abort()
  }, [canManage, playerId, reloadKey, versionNumber])

  const retry = useCallback(() => {
    setRequestState('loading')
    setErrorMessage(null)
    setReloadKey((key) => key + 1)
  }, [])

  const isLoading = canManage && requestState === 'loading'

  function handleSaved(next: PlayerAccountAssociationResponse) {
    setAssociation(next)
    setDialogMode(null)
    onAssociationChanged(next)
  }

  return (
    <section aria-labelledby="player-account-heading" className="border-t border-slate-200 px-5 py-6 sm:px-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3 id="player-account-heading" className="text-base font-bold text-slate-900">Account</h3>
          {isLoading ? (
            <p role="status" className="mt-2 text-sm text-slate-700">Loading linked account…</p>
          ) : errorMessage !== null ? (
            <div role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-950">
              <p>{errorMessage}</p>
              <button type="button" onClick={retry} className="mt-3 min-h-11 rounded-lg border border-red-800 bg-white px-4 font-semibold hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2">Retry</button>
            </div>
          ) : association?.account === null ? (
            <p className="mt-2 text-sm text-slate-700">No account linked</p>
          ) : association?.account !== undefined ? (
            <div className="mt-2">
              <p className="font-semibold text-slate-900">{association.account.display_name}</p>
              <p className="break-words text-sm text-slate-700">{association.account.email}</p>
              {!association.account.is_active ? <p className="mt-1 text-sm font-semibold text-amber-900">Account inactive</p> : null}
            </div>
          ) : null}
        </div>

        {canManage && !isLoading && errorMessage === null && association !== null ? (
          <div className="flex flex-wrap gap-2">
            {association.account === null ? (
              <button type="button" onClick={() => setDialogMode('link')} className="min-h-11 rounded-lg border border-academy bg-white px-4 text-sm font-semibold text-slate-900 hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2">Link account</button>
            ) : (
              <>
                <button type="button" onClick={() => setDialogMode('reassign')} className="min-h-11 rounded-lg border border-academy bg-white px-4 text-sm font-semibold text-slate-900 hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2">Reassign account</button>
                <button type="button" onClick={() => setDialogMode('unlink')} className="min-h-11 rounded-lg border border-red-800 bg-white px-4 text-sm font-semibold text-red-900 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2">Unlink account</button>
              </>
            )}
          </div>
        ) : null}
      </div>

      {dialogMode !== null && association !== null ? (
        <PlayerAccountLinkDialog
          mode={dialogMode}
          playerId={playerId}
          versionNumber={association.player_version_number}
          currentAccount={association.account}
          onClose={() => setDialogMode(null)}
          onConflict={() => {
            setDialogMode(null)
            retry()
          }}
          onSaved={handleSaved}
        />
      ) : null}
    </section>
  )
}
