import ModalDialog from '@shared/components/overlays/ModalDialog'
import {
  formatAcademyDateLabel,
  type CalendarDate,
} from '@shared/utils/calendarDate'
import type { CalendarEventInstance } from '../types/calendar'
import CalendarEventEntry from './CalendarEventEntry'

interface DayEventsModalProps {
  date: CalendarDate
  events: CalendarEventInstance[]
  onSelectEvent: (event: CalendarEventInstance) => void
  onClose: () => void
}

export default function DayEventsModal({
  date,
  events,
  onSelectEvent,
  onClose,
}: DayEventsModalProps) {
  const dateLabel = formatAcademyDateLabel(date)

  return (
    <ModalDialog labelledBy="calendar-day-events-title" onClose={onClose} testId="calendar-day-events">
      <div className="relative bg-white text-slate-900">
        <header className="border-b border-slate-200 px-5 py-4 pr-16 sm:px-6 sm:pr-16">
          <p className="text-sm font-semibold text-slate-600">Full day</p>
          <h2 id="calendar-day-events-title" className="mt-1 text-xl font-bold text-slate-900">{dateLabel}</h2>
        </header>
        <div className="px-5 py-5 sm:px-6">
          {events.length === 0 ? <p className="text-sm text-slate-600">No events scheduled for this day.</p> : null}
          {events.length > 0 ? (
            <ul className="divide-y divide-slate-200 border-y border-slate-200">
              {events.map((event) => (
                <li key={event.occurrence_id} className="py-1">
                  <CalendarEventEntry event={event} onSelect={onSelectEvent} />
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <button type="button" aria-label="Close full day events" data-modal-initial-focus className="absolute right-3 top-3 flex size-11 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 sm:right-4 sm:top-4" onClick={onClose}>
          <svg aria-hidden="true" className="size-6" fill="none" viewBox="0 0 24 24"><path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeLinecap="round" strokeWidth="2" /></svg>
        </button>
      </div>
    </ModalDialog>
  )
}
