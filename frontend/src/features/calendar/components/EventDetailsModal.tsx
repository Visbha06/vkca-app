import ModalDialog from '@shared/components/overlays/ModalDialog'
import { formatAcademyDateLabel, parseAcademyDate } from '@shared/utils/calendarDate'
import type { CalendarEventInstance } from '../types/calendar'
import {
  formatEventTime,
  getEventTypeLabel,
  getScopeLabel,
} from '../utils/calendarLabels'
import CalendarEventIcon from './CalendarEventIcon'

interface EventDetailsModalProps {
  event: CalendarEventInstance
  isLoading: boolean
  errorMessage: string | null
  onRetry: () => void
  onClose: () => void
  canManage?: boolean
  onEdit?: (event: CalendarEventInstance) => void
  onDelete?: (event: CalendarEventInstance) => void
}

export default function EventDetailsModal({
  event,
  isLoading,
  errorMessage,
  onRetry,
  onClose,
  canManage = false,
  onEdit,
  onDelete,
}: EventDetailsModalProps) {
  const parsedDate = parseAcademyDate(event.event_date)
  const dateLabel = parsedDate === null ? event.event_date : formatAcademyDateLabel(parsedDate)

  return (
    <ModalDialog
      describedBy="calendar-event-details-description"
      labelledBy="calendar-event-details-title"
      onClose={onClose}
      testId="calendar-event-details"
    >
      <div aria-busy={isLoading} className="relative bg-white text-slate-900">
        <header className="border-b border-slate-200 px-5 py-4 pr-16 sm:px-6 sm:pr-16">
          <div className="flex items-start gap-3">
            <span className="mt-1 flex size-10 shrink-0 items-center justify-center rounded-lg bg-academy/10 text-academy">
              <CalendarEventIcon eventType={event.event_type} className="size-6" />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-slate-600">{getEventTypeLabel(event.event_type)}</p>
              <h2 id="calendar-event-details-title" className="mt-1 break-words text-xl font-bold leading-7 text-slate-900">
                {event.name}
              </h2>
            </div>
          </div>
        </header>

        <div className="space-y-4 px-5 py-5 sm:px-6">
          {isLoading ? <p role="status" className="text-sm text-slate-600">Loading event details…</p> : null}
          {errorMessage !== null ? (
            <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-950">
              <p className="text-sm font-semibold">{errorMessage}</p>
              <button type="button" className="mt-3 min-h-11 rounded-lg border border-red-800 px-4 text-sm font-semibold hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2" onClick={onRetry}>
                Retry
              </button>
            </div>
          ) : null}
          <dl className="divide-y divide-slate-200 border-y border-slate-200">
            <div className="grid gap-1 py-3 sm:grid-cols-[minmax(0,8rem)_1fr] sm:gap-4">
              <dt className="text-sm font-semibold text-slate-600">Academy date</dt>
              <dd className="text-sm text-slate-900">{dateLabel}</dd>
            </div>
            <div className="grid gap-1 py-3 sm:grid-cols-[minmax(0,8rem)_1fr] sm:gap-4">
              <dt className="text-sm font-semibold text-slate-600">Time</dt>
              <dd className="text-sm text-slate-900">{formatEventTime(event.start_time, event.end_time)}</dd>
            </div>
            <div className="grid gap-1 py-3 sm:grid-cols-[minmax(0,8rem)_1fr] sm:gap-4">
              <dt className="text-sm font-semibold text-slate-600">Scope</dt>
              <dd className="text-sm text-slate-900">{getScopeLabel(event.scope_kind, event.age_groups)}</dd>
            </div>
            {event.is_recurring ? (
              <div className="grid gap-1 py-3 sm:grid-cols-[minmax(0,8rem)_1fr] sm:gap-4">
                <dt className="text-sm font-semibold text-slate-600">Repeats</dt>
                <dd className="text-sm text-slate-900">{event.recurrence_summary ?? 'Recurring event'}</dd>
              </div>
            ) : null}
          </dl>
          <p id="calendar-event-details-description" className="text-xs text-slate-600">Times shown in America/Los_Angeles academy time.</p>
          {canManage && !isLoading && errorMessage === null ? (
            <div className="flex flex-col-reverse gap-3 border-t border-slate-200 pt-5 sm:flex-row sm:justify-end">
              <button type="button" className="min-h-11 rounded-lg border border-red-700 bg-white px-4 text-sm font-semibold text-red-800 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2" onClick={() => onDelete?.(event)}>
                Delete Event
              </button>
              <button type="button" className="min-h-11 rounded-lg border border-academy bg-white px-4 text-sm font-semibold text-slate-900 hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2" onClick={() => onEdit?.(event)}>
                Edit Event
              </button>
            </div>
          ) : null}
        </div>
        <button type="button" aria-label="Close event details" data-modal-initial-focus className="absolute right-3 top-3 flex size-11 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 sm:right-4 sm:top-4" onClick={onClose}>
          <svg aria-hidden="true" className="size-6" fill="none" viewBox="0 0 24 24"><path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeLinecap="round" strokeWidth="2" /></svg>
        </button>
      </div>
    </ModalDialog>
  )
}
