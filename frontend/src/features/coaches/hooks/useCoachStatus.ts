import { useState } from 'react'
import { ApiClientError } from '@shared/api/client'
import {
  deactivateCoach,
  reactivateCoach,
} from '../api/coachApi'
import type { CoachResponse } from '../types/coach'
import useConflictHandler from './useConflictHandler'

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
  const [statusError, setStatusError] = useState<string | null>(null)

  const currentCoach =
    localCoach !== null &&
    localCoach.id === coach.id &&
    localCoach.version_number >= coach.version_number
      ? localCoach
      : coach
  const {
    conflictMessage,
    handleConflict,
    hasConflict,
    isReloading,
    reloadCoach,
  } = useConflictHandler({
    coach: currentCoach,
    onCoachReloaded: (latestCoach) => {
      setLocalCoach(latestCoach)
      setStatusError(null)
      onCoachReloaded?.(latestCoach)
    },
  })

  async function handleStatusChange(isActive: boolean) {
    if (isUpdatingStatus) return
    setIsUpdatingStatus(true)
    setStatusError(null)
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
      if (handleConflict(error)) {
        setStatusError(null)
      } else if (error instanceof ApiClientError && error.status === 403) {
        setStatusError('You do not have permission to change this account.')
      } else {
        setStatusError('Unable to update coach access. Please try again.')
      }
    } finally {
      setIsUpdatingStatus(false)
    }
  }

  return {
    conflictMessage,
    currentCoach,
    handleStatusChange,
    hasConflict,
    isReloading,
    isUpdatingStatus,
    reloadCoach,
    statusError,
  }
}
