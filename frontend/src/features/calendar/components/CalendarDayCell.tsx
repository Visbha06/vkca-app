import type { KeyboardEvent } from 'react'
import {
  calendarDateToIso,
  formatAcademyDateLabel,
  isSameCalendarDate,
  moveCalendarFocus,
  type CalendarDate,
  type CalendarMonth,
} from '@shared/utils/calendarDate'
import type { CalendarEventInstance } from '../types/calendar'
import CalendarEventEntry from './CalendarEventEntry'

interface CalendarDayCellProps {
  date: CalendarDate
  viewMonth: CalendarMonth
  academyToday: CalendarDate | null
  focusedDate: CalendarDate
  events: CalendarEventInstance[]
  onFocusDate: (date: CalendarDate) => void
  onSelectEvent: (event: CalendarEventInstance) => void
  onSelectMore: (date: CalendarDate, events: CalendarEventInstance[]) => void
}

function compareEvents(
  left: CalendarEventInstance,
  right: CalendarEventInstance,
) {
  const allDayOrder = Number(left.is_all_day) - Number(right.is_all_day)
  if (allDayOrder !== 0) return -allDayOrder
  const startOrder = (left.start_time ?? '').localeCompare(right.start_time ?? '')
  return startOrder || left.occurrence_id.localeCompare(right.occurrence_id)
}

export default function CalendarDayCell({
  date,
  viewMonth,
  academyToday,
  focusedDate,
  events,
  onFocusDate,
  onSelectEvent,
  onSelectMore,
}: CalendarDayCellProps) {
  const dateLabel = formatAcademyDateLabel(date)
  const outsideMonth = date.month !== viewMonth.month || date.year !== viewMonth.year
  const isToday = isSameCalendarDate(date, academyToday)
  const orderedEvents = [...events].sort(compareEvents)
  const visibleEvents = orderedEvents.slice(0, 3)
  const remainingCount = orderedEvents.length - visibleEvents.length

  function handleDateKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    const movementKeys = new Set([
      'ArrowLeft',
      'ArrowRight',
      'ArrowUp',
      'ArrowDown',
      'Home',
      'End',
    ])
    if (!movementKeys.has(event.key)) return
    event.preventDefault()
    onFocusDate(moveCalendarFocus(date, event.key as Parameters<typeof moveCalendarFocus>[1]))
  }

  return (
    <div
      role="gridcell"
      aria-label={`${dateLabel}${isToday ? ', current academy date' : ''}`}
      className={`min-w-0 border-b border-r border-slate-200 bg-white p-1 sm:p-2 ${outsideMonth ? 'bg-slate-50 text-slate-500' : ''}`}
      data-calendar-date={calendarDateToIso(date)}
      data-outside-month={outsideMonth ? 'true' : undefined}
    >
      <button
        type="button"
        aria-current={isToday ? 'date' : undefined}
        aria-label={isToday ? `Today, ${dateLabel}` : dateLabel}
        className={`flex min-h-11 min-w-11 items-center justify-center rounded-md border text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-academy focus:ring-inset ${
          isToday
            ? 'border-academy bg-academy/10 text-slate-950'
            : 'border-transparent text-slate-800 hover:bg-academy/10'
        } ${outsideMonth ? 'text-slate-500' : ''}`}
        data-calendar-date-button={calendarDateToIso(date)}
        data-outside-month={outsideMonth ? 'true' : undefined}
        onFocus={() => onFocusDate(date)}
        onKeyDown={handleDateKeyDown}
        tabIndex={isSameCalendarDate(date, focusedDate) ? 0 : -1}
      >
        {date.day}
      </button>
      <div className="mt-1 min-w-0 space-y-0.5">
        {visibleEvents.map((event) => (
          <CalendarEventEntry key={event.occurrence_id} event={event} onSelect={onSelectEvent} />
        ))}
        {remainingCount > 0 ? (
          <button
            type="button"
            className="min-h-11 w-full rounded-md px-1 text-left text-xs font-semibold text-academy underline-offset-2 hover:bg-academy/10 hover:underline focus:outline-none focus:ring-2 focus:ring-academy focus:ring-inset"
            aria-label={`${remainingCount} more ${remainingCount === 1 ? 'event' : 'events'} on ${dateLabel}`}
            onClick={() => onSelectMore(date, orderedEvents)}
          >
            +{remainingCount} more
          </button>
        ) : null}
      </div>
    </div>
  )
}
