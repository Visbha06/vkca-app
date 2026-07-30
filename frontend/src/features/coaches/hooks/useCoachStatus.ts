import { useState } from 'react'
import { ApiClientError } from '@shared/api/client'
import {
  deactivateCoach,
  fetchCoachDetails,
  reactivateCoach,
} from '../api/coachApi'
import type { CoachResponse } from '../types/coach'

interface UseCoachStatusOptions {
  coach: CoachResponse
  onCoachUpdated?: (coach: CoachResponse) => void
  onCoachReloaded?: (coach: CoachResponse) => void
}

export default function useCoachStatus({
  coach,
  onCoachUpdated,
  onCoachReloaded,
}: UseCoachStatusOptions) {
  const [localCoach, setLocalCoach] = useState<CoachResponse | null>(null)
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false)
  const [isReloading, setIsReloading] = useState(false)
  const [statusError, setStatusError] = useState<string | null>(null)
  const [hasConflict, setHasConflict] = useState(false)

  const currentCoach =
    localCoach !== null &&
    localCoach.id === coach.id &&
    localCoach.version_number >= coach.version_number
      ? localCoach
      : coach

  async function handleStatusChange(isActive: boolean) {
    if (isUpdatingStatus) return
    setIsUpdatingStatus(true)
    setStatusError(null)
    setHasConflict(false)
    try {
      const account = isActive
        ? await reactivateCoach(currentCoach.id, currentCoach.version_number)
        : await deactivateCoach(currentCoach.id, currentCoach.version_number)
      const updatedCoach: CoachResponse = {
        ...currentCoach,
        ...account,
        teams: currentCoach.teams,
      }
      setLocalCoach(updatedCoach)
      onCoachUpdated?.(updatedCoach)
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 409) {
        setHasConflict(true)
        setStatusError(
          'This coach was updated by another user. Reload the latest account before trying again.',
        )
      } else if (error instanceof ApiClientError && error.status === 403) {
        setStatusError('You do not have permission to change this account.')
      } else {
        setStatusError('Unable to update coach access. Please try again.')
      }
    } finally {
      setIsUpdatingStatus(false)
    }
  }

  async function reloadCoach() {
    if (isReloading) return
    setIsReloading(true)
    try {
      const latestCoach = await fetchCoachDetails(currentCoach.id)
      setLocalCoach(latestCoach)
      setStatusError(null)
      setHasConflict(false)
      onCoachReloaded?.(latestCoach)
    } catch {
      setStatusError('Unable to reload the latest coach. Please try again.')
    } finally {
      setIsReloading(false)
    }
  }

  return {
    currentCoach,
    handleStatusChange,
    hasConflict,
    isReloading,
    isUpdatingStatus,
    reloadCoach,
    statusError,
  }
}
