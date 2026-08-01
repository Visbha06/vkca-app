import { useCallback, useRef, useState } from 'react'
import {
  createCalendarEvent,
  updateCalendarOccurrence,
  updateCalendarSeries,
  updateStandaloneCalendarEvent,
} from '../api/calendarApi'
import type {
  CalendarEventCreatePayload,
  CalendarEventInstance,
  CalendarSeriesUpdatePayload,
} from '../types/calendar'
import {
  getCalendarErrorMessage,
  getExceptionRemovalWarning,
} from '../utils/calendarErrors'
import useCalendarConflict from './useCalendarConflict'

interface UseEventFormMutationOptions {
  event?: CalendarEventInstance
  onClose: () => void
  onDraftReset: () => void
  onEventReloaded: (event: CalendarEventInstance) => void
  onSaved: (message: string) => void
}

export default function useEventFormMutation({
  event,
  onClose,
  onDraftReset,
  onEventReloaded,
  onSaved,
}: UseEventFormMutationOptions) {
  const [currentEvent, setCurrentEvent] = useState(event ?? null)
  const [target, setTarget] = useState<'occurrence' | 'series'>('occurrence')
  const [revision, setRevision] = useState(0)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [pendingSeries, setPendingSeries] =
    useState<CalendarSeriesUpdatePayload | null>(null)
  const [warning, setWarning] = useState<ReturnType<
    typeof getExceptionRemovalWarning
  >>(null)
  const submissionInFlight = useRef(false)
  const conflict = useCalendarConflict({
    event: currentEvent,
    onReloaded: (latest) => {
      setCurrentEvent(latest)
      setRevision((value) => value + 1)
      setErrorMessage(null)
      onDraftReset()
      onEventReloaded(latest)
    },
  })

  const complete = useCallback((message: string) => {
    onSaved(message)
    onClose()
  }, [onClose, onSaved])

  async function submitSeries(payload: CalendarSeriesUpdatePayload) {
    if (currentEvent?.series_id === null || currentEvent === null) return
    try {
      await updateCalendarSeries(currentEvent.series_id, payload)
      complete('Event series updated.')
    } catch (error) {
      const nextWarning = getExceptionRemovalWarning(error)
      if (nextWarning !== null) {
        setWarning(nextWarning)
        setPendingSeries(payload)
      } else if (!conflict.handleConflict(error)) {
        setErrorMessage(
          getCalendarErrorMessage(
            error,
            'Unable to update this event. Please try again.',
          ),
        )
      }
    }
  }

  async function submit(values: CalendarEventCreatePayload) {
    if (submissionInFlight.current || conflict.hasConflict) return
    submissionInFlight.current = true
    setIsSubmitting(true)
    setErrorMessage(null)
    const { recurrence, ...eventValues } = values
    try {
      if (currentEvent === null) {
        await createCalendarEvent(values)
        complete('Event created.')
      } else if (!currentEvent.is_recurring) {
        await updateStandaloneCalendarEvent(currentEvent.event_id, {
          ...eventValues,
          version_number: currentEvent.event_version_number,
        })
        complete('Event updated.')
      } else if (target === 'occurrence') {
        await updateCalendarOccurrence(currentEvent.occurrence_id, {
          ...eventValues,
          version_number: currentEvent.event_version_number,
          exception_version_number: currentEvent.exception_version_number,
        })
        complete('Occurrence updated. The rest of the series is unchanged.')
      } else if (recurrence === null) {
        setErrorMessage('A recurring series must keep a recurrence rule.')
      } else {
        await submitSeries({
          ...eventValues,
          recurrence,
          version_number: currentEvent.event_version_number,
          confirm_exception_removals: false,
        })
      }
    } catch (error) {
      if (!conflict.handleConflict(error)) {
        setErrorMessage(
          getCalendarErrorMessage(
            error,
            `Unable to ${currentEvent === null ? 'create' : 'update'} this event. Please try again.`,
          ),
        )
      }
    } finally {
      submissionInFlight.current = false
      setIsSubmitting(false)
    }
  }

  async function confirmSeriesUpdate() {
    if (pendingSeries === null || submissionInFlight.current) return
    submissionInFlight.current = true
    setIsSubmitting(true)
    setWarning(null)
    setPendingSeries(null)
    try {
      await submitSeries({
        ...pendingSeries,
        confirm_exception_removals: true,
      })
    } finally {
      submissionInFlight.current = false
      setIsSubmitting(false)
    }
  }

  const cancelWarning = useCallback(() => {
    setWarning(null)
    setPendingSeries(null)
  }, [])

  return {
    cancelWarning,
    confirmSeriesUpdate,
    conflict,
    currentEvent,
    errorMessage,
    isSubmitting,
    isUnsafeToClose: () => submissionInFlight.current || conflict.isReloading,
    revision,
    setErrorMessage,
    setTarget,
    submit,
    target,
    warning,
  }
}
