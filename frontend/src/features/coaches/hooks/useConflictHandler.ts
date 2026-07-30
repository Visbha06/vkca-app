import { useCallback, useState } from 'react'
import { ApiClientError } from '@shared/api/client'
import { fetchCoachDetails } from '../api/coachApi'
import type { CoachResponse } from '../types/coach'

const CONFLICT_MESSAGE =
  'This coach was updated by another user. Reload the latest account before trying again.'

interface UseConflictHandlerOptions {
  coach: CoachResponse
  onCoachReloaded?: (coach: CoachResponse) => void
}

export default function useConflictHandler({
  coach,
  onCoachReloaded,
}: UseConflictHandlerOptions) {
  const [staleCoach, setStaleCoach] = useState<CoachResponse | null>(null)
  const [reloadError, setReloadError] = useState<string | null>(null)
  const [isReloading, setIsReloading] = useState(false)

  const handleConflict = useCallback(
    (error: unknown) => {
      if (!(error instanceof ApiClientError) || error.status !== 409) {
        return false
      }

      setStaleCoach(coach)
      setReloadError(null)
      return true
    },
    [coach],
  )

  const clearConflict = useCallback(() => {
    setStaleCoach(null)
    setReloadError(null)
  }, [])

  const reloadCoach = useCallback(async () => {
    if (isReloading || staleCoach === null) return null

    setIsReloading(true)
    setReloadError(null)
    try {
      const latestCoach = await fetchCoachDetails(staleCoach.id)
      clearConflict()
      onCoachReloaded?.(latestCoach)
      return latestCoach
    } catch {
      setReloadError('Unable to reload the latest coach. Please try again.')
      return null
    } finally {
      setIsReloading(false)
    }
  }, [clearConflict, isReloading, onCoachReloaded, staleCoach])

  return {
    clearConflict,
    conflictMessage:
      staleCoach === null ? null : (reloadError ?? CONFLICT_MESSAGE),
    handleConflict,
    hasConflict: staleCoach !== null,
    isReloading,
    reloadCoach,
    staleCoach,
  }
}
