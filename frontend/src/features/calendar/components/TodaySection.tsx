import CalendarEventEntry from './CalendarEventEntry'
import { formatAcademyDateLabel, parseAcademyDate } from '@shared/utils/calendarDate'
import type { CalendarEventInstance } from '../types/calendar'

interface TodaySectionProps {
  academyToday: string | null
  events: CalendarEventInstance[]
  isLoading: boolean
  errorMessage: string | null
  onRetry: () => void
  onSelectEvent: (event: CalendarEventInstance) => void
}

function compareEvents(
  left: CalendarEventInstance,
  right: CalendarEventInstance,
) {
  const allDayOrder = Number(left.is_all_day) - Number(right.is_all_day)
  if (allDayOrder !== 0) return -allDayOrder
  return (
    (left.start_time ?? '').localeCompare(right.start_time ?? '') ||
    left.occurrence_id.localeCompare(right.occurrence_id)
  )
}

export default function TodaySection({
  academyToday,
  events,
  isLoading,
  errorMessage,
  onRetry,
  onSelectEvent,
}: TodaySectionProps) {
  const parsedDate = academyToday === null ? null : parseAcademyDate(academyToday)
  const dateLabel = parsedDate === null ? 'Academy today' : formatAcademyDateLabel(parsedDate)
  const orderedEvents = [...events].sort(compareEvents)

  return (
    <section aria-labelledby="today-heading" className="border-t border-slate-200 pt-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 id="today-heading" className="text-xl font-bold text-slate-900">Today</h2>
          <p className="mt-1 text-sm text-slate-600">{dateLabel}</p>
        </div>
        {isLoading ? <span className="text-sm font-semibold text-slate-600">Updating</span> : null}
      </div>

      {isLoading ? (
        <p role="status" aria-label="Loading Today" className="mt-4 rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-600">
          Loading Today…
        </p>
      ) : null}
      {!isLoading && errorMessage !== null ? (
        <div role="alert" className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 text-red-950">
          <p className="text-sm font-semibold">{errorMessage}</p>
          <button
            type="button"
            className="mt-3 min-h-11 rounded-lg border border-red-800 px-4 text-sm font-semibold hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2"
            onClick={onRetry}
          >
            Retry Today
          </button>
        </div>
      ) : null}
      {!isLoading && errorMessage === null && orderedEvents.length === 0 ? (
        <p className="mt-4 rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-600">
          No events scheduled for today.
        </p>
      ) : null}
      {!isLoading && errorMessage === null && orderedEvents.length > 0 ? (
        <div className="mt-4 overflow-hidden rounded-lg border border-slate-200 bg-white" aria-label="Today events">
          <ul className="divide-y divide-slate-200">
            {orderedEvents.map((event) => (
              <li key={event.occurrence_id} className="flex min-w-0 items-center gap-2 px-3 py-1 sm:px-4">
                <div className="min-w-0 flex-1">
                  <CalendarEventEntry event={event} onSelect={onSelectEvent} />
                  {event.is_recurring && event.recurrence_summary !== null ? (
                    <p className="pb-2 pl-6 text-xs text-slate-600">{event.recurrence_summary}</p>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}
