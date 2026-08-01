import CalendarEventIcon from './CalendarEventIcon'
import {
  formatEventTime,
  getEventAccessibleLabel,
  getEventTypeLabel,
} from '../utils/calendarLabels'
import type { CalendarEventInstance } from '../types/calendar'

interface CalendarEventEntryProps {
  event: CalendarEventInstance
  onSelect: (event: CalendarEventInstance) => void
}

export default function CalendarEventEntry({
  event,
  onSelect,
}: CalendarEventEntryProps) {
  return (
    <button
      type="button"
      className="flex min-h-11 w-full min-w-0 items-center gap-1 rounded-md px-1 text-left text-xs font-semibold text-slate-800 hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-inset"
      aria-label={getEventAccessibleLabel(event)}
      data-calendar-event={event.occurrence_id}
      onClick={() => onSelect(event)}
    >
      <CalendarEventIcon eventType={event.event_type} className="size-4 shrink-0 text-academy" />
      <span className="min-w-0 flex-1 truncate">
        <span className="sr-only">{getEventTypeLabel(event.event_type)}: </span>
        <span className="block truncate">{event.name}</span>
        <span className="block truncate font-normal text-slate-600">
          {formatEventTime(event.start_time, event.end_time)}
        </span>
      </span>
    </button>
  )
}
