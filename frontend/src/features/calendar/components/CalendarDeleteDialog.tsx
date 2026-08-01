import { useState } from 'react'
import { ApiClientError } from '@shared/api/client'
import ModalDialog from '@shared/components/overlays/ModalDialog'
import {
  deleteCalendarOccurrence,
  deleteCalendarSeries,
  deleteStandaloneCalendarEvent,
} from '../api/calendarApi'
import useCalendarConflict from '../hooks/useCalendarConflict'
import type { CalendarEventInstance } from '../types/calendar'
import { getCalendarErrorMessage } from '../utils/calendarErrors'

interface CalendarDeleteDialogProps {
  event: CalendarEventInstance
  onClose: () => void
  onDeleted: (message: string) => void
  onEventReloaded: (event: CalendarEventInstance) => void
}

export default function CalendarDeleteDialog({
  event,
  onClose,
  onDeleted,
  onEventReloaded,
}: CalendarDeleteDialogProps) {
  const [currentEvent, setCurrentEvent] = useState(event)
  const [target, setTarget] = useState<'occurrence' | 'series'>('occurrence')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const conflict = useCalendarConflict({
    event: currentEvent,
    onReloaded: (latest) => {
      setCurrentEvent(latest)
      setErrorMessage(null)
      onEventReloaded(latest)
    },
  })

  async function handleDelete() {
    if (isSubmitting) return
    setIsSubmitting(true)
    setErrorMessage(null)
    try {
      if (!currentEvent.is_recurring) {
        await deleteStandaloneCalendarEvent(currentEvent.event_id, {
          version_number: currentEvent.event_version_number,
        })
        onDeleted('Event deleted.')
      } else if (target === 'occurrence') {
        await deleteCalendarOccurrence(currentEvent.occurrence_id, {
          version_number: currentEvent.event_version_number,
          exception_version_number: currentEvent.exception_version_number,
        })
        onDeleted('Occurrence deleted. The rest of the series is unchanged.')
      } else {
        await deleteCalendarSeries(currentEvent.series_id!, {
          version_number: currentEvent.event_version_number,
        })
        onDeleted('Event series deleted.')
      }
    } catch (error) {
      if (conflict.handleConflict(error)) return
      setErrorMessage(
        getCalendarErrorMessage(error, 'Unable to delete this event. Please try again.'),
      )
      if (error instanceof ApiClientError && error.status === 404) {
        onEventReloaded(currentEvent)
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  function handleClose() {
    if (!isSubmitting && !conflict.isReloading) onClose()
  }

  return (
    <ModalDialog labelledBy="calendar-delete-title" onClose={handleClose} testId="calendar-delete-dialog">
      <div className="relative bg-white p-5 text-slate-900 sm:p-6">
        <h2 id="calendar-delete-title" className="pr-12 text-xl font-bold">
          Delete {currentEvent.name}?
        </h2>
        <p className="mt-2 max-w-prose text-sm leading-6 text-slate-700">
          This action cannot be undone.
        </p>
        {currentEvent.is_recurring ? (
          <fieldset className="mt-5 space-y-2">
            <legend className="text-sm font-semibold text-slate-900">Delete</legend>
            <label className="flex min-h-11 items-center gap-3 rounded-lg border border-slate-200 px-3 text-sm text-slate-800">
              <input type="radio" name="delete-target" value="occurrence" checked={target === 'occurrence'} disabled={isSubmitting} className="size-5 text-academy focus:ring-academy" onChange={() => setTarget('occurrence')} />
              This occurrence only
            </label>
            <label className="flex min-h-11 items-center gap-3 rounded-lg border border-slate-200 px-3 text-sm text-slate-800">
              <input type="radio" name="delete-target" value="series" checked={target === 'series'} disabled={isSubmitting} className="size-5 text-academy focus:ring-academy" onChange={() => setTarget('series')} />
              Entire series
            </label>
          </fieldset>
        ) : null}
        {(errorMessage ?? conflict.conflictMessage) !== null ? (
          <div role="alert" className="mt-5 rounded-lg border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-950">
            {errorMessage ?? conflict.conflictMessage}
            {conflict.hasConflict ? (
              <button type="button" disabled={conflict.isReloading} className="mt-3 block min-h-11 rounded-lg border border-red-800 bg-white px-4 text-sm font-semibold hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2" onClick={() => void conflict.reload()}>
                {conflict.isReloading ? 'Reloading event…' : 'Reload latest event'}
              </button>
            ) : null}
          </div>
        ) : null}
        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button type="button" data-modal-initial-focus disabled={isSubmitting} className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2" onClick={handleClose}>Cancel</button>
          <button type="button" disabled={isSubmitting || conflict.hasConflict} className="min-h-11 rounded-lg bg-red-800 px-4 text-sm font-semibold text-white hover:bg-red-900 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2 disabled:bg-red-300" onClick={() => void handleDelete()}>
            {isSubmitting ? 'Deleting event…' : target === 'series' ? 'Delete entire series' : 'Delete event'}
          </button>
        </div>
        {isSubmitting ? <p role="status" className="sr-only">Deleting calendar event</p> : null}
      </div>
    </ModalDialog>
  )
}
