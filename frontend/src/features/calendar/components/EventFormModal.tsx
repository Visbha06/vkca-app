import { useCallback, useMemo, useState } from 'react'
import { useUnsavedChanges } from '@shared/hooks/useUnsavedChanges'
import useEventFormMutation from '../hooks/useEventFormMutation'
import type { CalendarEventInstance } from '../types/calendar'
import { calendarEventToForm, emptyCalendarForm } from '../utils/calendarForm'
import EventFormModalContent from './EventFormModalContent'

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
  const [isDirty, setIsDirty] = useState(false)
  const [showDiscardConfirmation, setShowDiscardConfirmation] = useState(false)
  const mutation = useEventFormMutation({
    event,
    onClose,
    onDraftReset: () => {
      setIsDirty(false)
      setShowDiscardConfirmation(false)
    },
    onEventReloaded,
    onSaved,
  })
  const initialValues = useMemo(
    () =>
      mutation.currentEvent === null
        ? emptyCalendarForm(academyToday)
        : calendarEventToForm(
            mutation.currentEvent,
            mutation.currentEvent.is_recurring && mutation.target === 'series'
              ? 'series'
              : 'occurrence',
          ),
    [academyToday, mutation.currentEvent, mutation.target],
  )
  const isCreating = mutation.currentEvent === null
  const editingSeries =
    mutation.currentEvent?.is_recurring === true && mutation.target === 'series'
  const allowRecurrence = isCreating || editingSeries
  const requestClose = useUnsavedChanges(
    isDirty,
    onClose,
    () => setShowDiscardConfirmation(true),
  )

  const restoreFormFocus = useCallback(() => {
    requestAnimationFrame(() => {
      document.getElementById('calendar-event-name')?.focus()
    })
  }, [])

  const cancelWarning = useCallback(() => {
    mutation.cancelWarning()
    restoreFormFocus()
  }, [mutation, restoreFormFocus])

  const handleClose = useCallback(() => {
    if (mutation.isUnsafeToClose()) return
    if (showDiscardConfirmation) {
      setShowDiscardConfirmation(false)
      restoreFormFocus()
      return
    }
    if (mutation.warning !== null) {
      cancelWarning()
      return
    }
    requestClose()
  }, [
    cancelWarning,
    mutation,
    requestClose,
    restoreFormFocus,
    showDiscardConfirmation,
  ])

  const conflictAction = mutation.conflict.hasConflict ? (
    <button type="button" disabled={mutation.conflict.isReloading} className="mt-3 block min-h-11 rounded-lg border border-red-800 bg-white px-4 text-sm font-semibold hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2" onClick={() => void mutation.conflict.reload()}>
      {mutation.conflict.isReloading ? 'Reloading event…' : 'Reload latest event'}
    </button>
  ) : undefined

  const dialogLabel = showDiscardConfirmation
    ? 'calendar-unsaved-title'
    : mutation.warning !== null
      ? 'series-exception-warning-title'
      : 'calendar-event-form-title'
  const dialogDescription = showDiscardConfirmation
    ? 'calendar-unsaved-description'
    : mutation.warning !== null
      ? 'series-exception-warning-description'
      : 'calendar-event-form-description'

  return (
    <EventFormModalContent
      academyToday={academyToday}
      allowRecurrence={allowRecurrence}
      currentEvent={mutation.currentEvent}
      dialogDescription={dialogDescription}
      dialogLabel={dialogLabel}
      editingSeries={editingSeries}
      errorAction={conflictAction}
      errorMessage={mutation.conflict.conflictMessage ?? mutation.errorMessage}
      initialValues={initialValues}
      isBlocked={mutation.conflict.hasConflict || mutation.conflict.isReloading}
      isCreating={isCreating}
      isReloading={mutation.conflict.isReloading}
      isSubmitting={mutation.isSubmitting}
      onCancelWarning={cancelWarning}
      onClose={handleClose}
      onConfirmSeriesUpdate={() => void mutation.confirmSeriesUpdate()}
      onContinueEditing={() => {
        setShowDiscardConfirmation(false)
        restoreFormFocus()
      }}
      onDirtyChange={setIsDirty}
      onDiscard={onClose}
      onFormChange={() => mutation.setErrorMessage(null)}
      onSubmit={(values) => void mutation.submit(values)}
      onTargetChange={mutation.setTarget}
      revision={mutation.revision}
      showDiscardConfirmation={showDiscardConfirmation}
      target={mutation.target}
      warning={mutation.warning}
    />
  )
}
