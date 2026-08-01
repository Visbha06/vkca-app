import { useCallback, useState } from 'react'
import { ApiClientError } from '@shared/api/client'
import { fetchCalendarInstance } from '../api/calendarApi'
import type { CalendarEventInstance } from '../types/calendar'

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
    if (event === null || isReloading) return null
    setIsReloading(true)
    setReloadError(null)
    try {
      const latest = await fetchCalendarInstance(event.occurrence_id)
      clearConflict()
      onReloaded(latest)
      return latest
    } catch {
      setReloadError('Unable to reload the latest event. Please try again.')
      return null
    } finally {
      setIsReloading(false)
    }
  }, [clearConflict, event, isReloading, onReloaded])

  return {
    clearConflict,
    conflictMessage: hasConflict ? (reloadError ?? conflictCopy) : null,
    handleConflict,
    hasConflict,
    isReloading,
    reload,
  }
}
