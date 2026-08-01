import { useCallback, useMemo, useState } from 'react'
import ModalDialog from '@shared/components/overlays/ModalDialog'
import { useUnsavedChanges } from '@shared/hooks/useUnsavedChanges'
import {
  createCalendarEvent,
  updateCalendarOccurrence,
  updateCalendarSeries,
  updateStandaloneCalendarEvent,
} from '../api/calendarApi'
import useCalendarConflict from '../hooks/useCalendarConflict'
import type {
  CalendarEventCreatePayload,
  CalendarEventInstance,
  CalendarSeriesUpdatePayload,
} from '../types/calendar'
import { getCalendarErrorMessage, getExceptionRemovalWarning } from '../utils/calendarErrors'
import { calendarEventToForm, emptyCalendarForm } from '../utils/calendarForm'
import EventForm from './EventForm'
import EventFormModalHeader from './EventFormModalHeader'
import SeriesExceptionWarning from './SeriesExceptionWarning'

interface EventFormModalProps {
  academyToday: string
  event?: CalendarEventInstance
  onClose: () => void
  onSaved: (message: string) => void
  onEventReloaded: (event: CalendarEventInstance) => void
}

export default function EventFormModal({
  academyToday,
  event,
  onClose,
  onSaved,
  onEventReloaded,
}: EventFormModalProps) {
  const [currentEvent, setCurrentEvent] = useState(event ?? null)
  const [target, setTarget] = useState<'occurrence' | 'series'>('occurrence')
  const [revision, setRevision] = useState(0)
  const [isDirty, setIsDirty] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [pendingSeries, setPendingSeries] =
    useState<CalendarSeriesUpdatePayload | null>(null)
  const [warning, setWarning] = useState<ReturnType<
    typeof getExceptionRemovalWarning
  >>(null)
  const conflict = useCalendarConflict({
    event: currentEvent,
    onReloaded: (latest) => {
      setCurrentEvent(latest)
      setRevision((value) => value + 1)
      setIsDirty(false)
      setErrorMessage(null)
      onEventReloaded(latest)
    },
  })
  const initialValues = useMemo(
    () =>
      currentEvent === null
        ? emptyCalendarForm(academyToday)
        : calendarEventToForm(
            currentEvent,
            currentEvent.is_recurring && target === 'series'
              ? 'series'
              : 'occurrence',
          ),
    [academyToday, currentEvent, target],
  )
  const isCreating = currentEvent === null
  const editingSeries = currentEvent?.is_recurring === true && target === 'series'
  const allowRecurrence = isCreating || editingSeries
  const requestClose = useUnsavedChanges(isDirty, onClose)

  const handleClose = useCallback(() => {
    if (isSubmitting || conflict.isReloading) return
    if (warning !== null) {
      setWarning(null)
      setPendingSeries(null)
      return
    }
    requestClose()
  }, [conflict.isReloading, isSubmitting, requestClose, warning])

  function complete(message: string) {
    onSaved(message)
    onClose()
  }

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
          getCalendarErrorMessage(error, 'Unable to update this event. Please try again.'),
        )
      }
    }
  }

  async function handleSubmit(values: CalendarEventCreatePayload) {
    if (isSubmitting || conflict.hasConflict) return
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
            `Unable to ${isCreating ? 'create' : 'update'} this event. Please try again.`,
          ),
        )
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  async function confirmSeriesUpdate() {
    if (pendingSeries === null || isSubmitting) return
    setIsSubmitting(true)
    await submitSeries({ ...pendingSeries, confirm_exception_removals: true })
    setIsSubmitting(false)
  }

  const conflictAction = conflict.hasConflict ? (
    <button type="button" disabled={conflict.isReloading} className="mt-3 block min-h-11 rounded-lg border border-red-800 bg-white px-4 text-sm font-semibold hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2" onClick={() => void conflict.reload()}>
      {conflict.isReloading ? 'Reloading event…' : 'Reload latest event'}
    </button>
  ) : undefined

  return (
    <ModalDialog labelledBy={warning === null ? 'calendar-event-form-title' : 'series-exception-warning-title'} onClose={handleClose} testId="calendar-event-form-modal">
      {warning !== null ? (
        <SeriesExceptionWarning warning={warning} isSubmitting={isSubmitting} onCancel={() => { setWarning(null); setPendingSeries(null) }} onContinue={() => void confirmSeriesUpdate()} />
      ) : (
        <div className="relative bg-white text-slate-900">
          <EventFormModalHeader
            isCreating={isCreating}
            isRecurring={currentEvent?.is_recurring ?? false}
            target={target}
            disabled={isSubmitting || conflict.isReloading}
            onTargetChange={setTarget}
            onClose={handleClose}
          />
          <EventForm
            key={`${currentEvent?.occurrence_id ?? 'create'}-${target}-${revision}`}
            initialValues={initialValues}
            academyToday={academyToday}
            allowRecurrence={allowRecurrence}
            allowUnchangedPast={!isCreating}
            recurrenceRequired={editingSeries}
            isSubmitting={isSubmitting}
            isBlocked={conflict.hasConflict || conflict.isReloading}
            errorMessage={conflict.conflictMessage ?? errorMessage}
            errorAction={conflictAction}
            submitLabel={isCreating ? 'Create event' : 'Save changes'}
            onCancel={handleClose}
            onChange={() => setErrorMessage(null)}
            onDirtyChange={setIsDirty}
            onSubmit={(values) => void handleSubmit(values)}
          />
        </div>
      )}
    </ModalDialog>
  )
}
