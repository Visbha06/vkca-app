import { useCallback, useEffect, useState } from 'react'
import { ApiClientError } from '@shared/api/client'
import { isAbortError } from '@shared/api/errors'
import {
  fetchEligiblePlayerAccounts,
  linkPlayerAccount,
  reassignPlayerAccount,
  unlinkPlayerAccount,
} from '../../api/playerApi'
import type {
  PlayerAccountAssociationResponse,
  PlayerAccountSnapshot,
} from '../../types/player'

export type PlayerAccountDialogMode = 'link' | 'reassign' | 'unlink'

interface DialogOptions {
  mode: PlayerAccountDialogMode
  playerId: string
  versionNumber: number
  currentAccount: PlayerAccountSnapshot | null
  onSaved: (association: PlayerAccountAssociationResponse) => void
}

export default function usePlayerAccountDialog({
  mode,
  playerId,
  versionNumber,
  currentAccount,
  onSaved,
}: DialogOptions) {
  const [accounts, setAccounts] = useState<PlayerAccountSnapshot[]>([])
  const [search, setSearch] = useState('')
  const [requestedSearch, setRequestedSearch] = useState('')
  const [searchRevision, setSearchRevision] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(mode !== 'unlink')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [hasConflict, setHasConflict] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const isDirty = search !== '' || selectedId !== null

  useEffect(() => {
    if (mode === 'unlink') return
    const controller = new AbortController()
    void fetchEligiblePlayerAccounts(
      { search: requestedSearch, page: 1, pageSize: 20 },
      controller.signal,
    )
      .then((response) => {
        if (!controller.signal.aborted) setAccounts(response.users)
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && !isAbortError(error)) {
          setErrorMessage('Unable to load eligible Player accounts. Please try again.')
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false)
      })
    return () => controller.abort()
  }, [mode, requestedSearch, searchRevision])

  const submit = useCallback(async () => {
    if (isSubmitting) return
    if (mode !== 'unlink' && selectedId === null) return
    setIsSubmitting(true)
    setHasConflict(false)
    setErrorMessage(null)
    try {
      const association =
        mode === 'link'
          ? await linkPlayerAccount(playerId, {
              user_id: selectedId!,
              version_number: versionNumber,
            })
          : mode === 'reassign'
            ? await reassignPlayerAccount(playerId, {
                expected_user_id: currentAccount!.id,
                new_user_id: selectedId!,
                version_number: versionNumber,
              })
            : await unlinkPlayerAccount(playerId, {
                version_number: versionNumber,
              })
      onSaved(association)
    } catch (error) {
      const conflict = error instanceof ApiClientError && error.status === 409
      setHasConflict(conflict)
      setErrorMessage(
        conflict
          ? 'The linked account changed. Reload the latest Player before retrying.'
          : error instanceof ApiClientError && error.status === 403
            ? 'Only a Head Coach can change Player account links.'
            : 'Unable to save the account link. Please try again.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }, [currentAccount, isSubmitting, mode, onSaved, playerId, selectedId, versionNumber])

  return {
    accounts,
    errorMessage,
    hasConflict,
    isDirty,
    isLoading,
    isSubmitting,
    search,
    selectedId,
    setSearch: (value: string) => {
      setSearch(value)
      setSelectedId(null)
    },
    setSelectedId,
    submit,
    searchAccounts: () => {
      setIsLoading(true)
      setErrorMessage(null)
      setRequestedSearch(search.trim())
      setSearchRevision((revision) => revision + 1)
    },
  }
}
