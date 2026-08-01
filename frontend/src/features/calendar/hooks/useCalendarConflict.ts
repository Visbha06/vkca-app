import { useCallback, useRef, useState } from 'react'
import { ApiClientError } from '@shared/api/client'
import { fetchCalendarInstance } from '../api/calendarApi'
import type { CalendarEventInstance } from '../types/calendar'
import { getCalendarErrorMessage } from '../utils/calendarErrors'

const conflictCopy =
  'This event changed since you opened it. Reload the latest event before trying again.'

interface UseCalendarConflictOptions {
  event: CalendarEventInstance | null
  onReloaded: (event: CalendarEventInstance) => void
}

export default function useCalendarConflict({
  event,
  onReloaded,
}: UseCalendarConflictOptions) {
  const [hasConflict, setHasConflict] = useState(false)
  const [isReloading, setIsReloading] = useState(false)
  const [reloadError, setReloadError] = useState<string | null>(null)
  const reloadInFlight = useRef(false)

  const handleConflict = useCallback((error: unknown) => {
    if (!(error instanceof ApiClientError) || error.status !== 409) return false
    setHasConflict(true)
    setReloadError(null)
    return true
  }, [])

  const clearConflict = useCallback(() => {
    setHasConflict(false)
    setReloadError(null)
  }, [])

  const reload = useCallback(async () => {
    if (event === null || reloadInFlight.current) return null
    reloadInFlight.current = true
    setIsReloading(true)
    setReloadError(null)
    try {
      const latest = await fetchCalendarInstance(event.occurrence_id)
      clearConflict()
      onReloaded(latest)
      return latest
    } catch (error) {
      setReloadError(
        getCalendarErrorMessage(
          error,
          'Unable to reload the latest event. Please try again.',
        ),
      )
      return null
    } finally {
      reloadInFlight.current = false
      setIsReloading(false)
    }
  }, [clearConflict, event, onReloaded])

  return {
    clearConflict,
    conflictMessage: hasConflict ? (reloadError ?? conflictCopy) : null,
    handleConflict,
    hasConflict,
    isReloading,
    reload,
  }
}
