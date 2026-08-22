import type { ReactNode } from 'react'
import ModalDialog from '@shared/components/overlays/ModalDialog'
import UnsavedChangesPrompt from '@shared/components/overlays/UnsavedChangesPrompt'
import type {
  CalendarEventCreatePayload,
  CalendarEventInstance,
  ExceptionRemovalWarningResponse,
} from '../types/calendar'
import EventForm from './EventForm'
import EventFormModalHeader from './EventFormModalHeader'
import SeriesExceptionWarning from './SeriesExceptionWarning'

interface EventFormModalContentProps {
  academyToday: string
  allowRecurrence: boolean
  currentEvent: CalendarEventInstance | null
  dialogDescription: string
  dialogLabel: string
  editingSeries: boolean
  errorAction?: ReactNode
  errorMessage: string | null
  initialValues: CalendarEventCreatePayload
  isBlocked: boolean
  isCreating: boolean
  isReloading: boolean
  isSubmitting: boolean
  onCancelWarning: () => void
  onClose: () => void
  onConfirmSeriesUpdate: () => void
  onContinueEditing: () => void
  onDirtyChange: (isDirty: boolean) => void
  onDiscard: () => void
  onFormChange: () => void
  onSubmit: (values: CalendarEventCreatePayload) => void
  onTargetChange: (target: 'occurrence' | 'series') => void
  revision: number
  showDiscardConfirmation: boolean
  target: 'occurrence' | 'series'
  warning: ExceptionRemovalWarningResponse | null
}

export default function EventFormModalContent({
  academyToday,
  allowRecurrence,
  currentEvent,
  dialogDescription,
  dialogLabel,
  editingSeries,
  errorAction,
  errorMessage,
  initialValues,
  isBlocked,
  isCreating,
  isReloading,
  isSubmitting,
  onCancelWarning,
  onClose,
  onConfirmSeriesUpdate,
  onContinueEditing,
  onDirtyChange,
  onDiscard,
  onFormChange,
  onSubmit,
  onTargetChange,
  revision,
  showDiscardConfirmation,
  target,
  warning,
}: EventFormModalContentProps) {
  const confirmationVisible = warning !== null || showDiscardConfirmation

  return (
    <ModalDialog
      describedBy={dialogDescription}
      labelledBy={dialogLabel}
      onClose={onClose}
      role={confirmationVisible ? 'alertdialog' : 'dialog'}
      testId="calendar-event-form-modal"
    >
      {showDiscardConfirmation ? (
        <UnsavedChangesPrompt
          title="Discard unsaved changes?"
          titleId="calendar-unsaved-title"
          description="Discarding will remove the calendar changes you made in this form."
          descriptionId="calendar-unsaved-description"
          onContinueEditing={onContinueEditing}
          onDiscard={onDiscard}
        />
      ) : null}
      {warning !== null ? (
        <SeriesExceptionWarning
          warning={warning}
          isSubmitting={isSubmitting}
          onCancel={onCancelWarning}
          onContinue={onConfirmSeriesUpdate}
        />
      ) : null}
      <div
        className="relative bg-white text-slate-900"
        hidden={confirmationVisible}
        inert={confirmationVisible}
      >
        <EventFormModalHeader
          isCreating={isCreating}
          isRecurring={currentEvent?.is_recurring ?? false}
          target={target}
          disabled={isSubmitting || isReloading}
          onTargetChange={onTargetChange}
          onClose={onClose}
        />
        <EventForm
          key={`${currentEvent?.occurrence_id ?? 'create'}-${target}-${revision}`}
          initialValues={initialValues}
          academyToday={academyToday}
          allowRecurrence={allowRecurrence}
          allowUnchangedPast={!isCreating}
          recurrenceRequired={editingSeries}
          isSubmitting={isSubmitting}
          isBlocked={isBlocked}
          errorMessage={errorMessage}
          errorAction={errorAction}
          submitLabel={isCreating ? 'Create event' : 'Save changes'}
          onCancel={onClose}
          onChange={onFormChange}
          onDirtyChange={onDirtyChange}
          onSubmit={onSubmit}
        />
      </div>
    </ModalDialog>
  )
}
