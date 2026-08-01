import type { FocusEvent, KeyboardEvent } from 'react'
import {
  calendarDateToIso,
  formatAcademyDateLabel,
  isCalendarDateInMonth,
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

/**
 * Date state matrix (selection is intentionally absent because dates are not selectable):
 * - Normal: white cell, slate-800 number, academy-wash hover.
 * - Out of month: slate-50 cell, slate-500 number, slate-700 on academy-wash hover.
 * - Today: academy border and wash, slate-950 number, aria-current="date".
 * - Focus: inset slate-900 ring on every date state (17.85:1 on white; 16.19:1 on wash).
 * - Today + focus: today surface/border remain visible beneath the dark focus ring.
 */
const DATE_CELL_STYLES = {
  normal: 'bg-white',
  outsideMonth: 'bg-slate-50 text-slate-500',
} as const

const DATE_NUMBER_STYLES = {
  normal: 'border-transparent text-slate-800 hover:bg-academy/10',
  outsideMonth:
    'border-transparent text-slate-500 hover:bg-academy/10 hover:text-slate-700',
  today: 'border-academy bg-academy/10 text-slate-950',
} as const

const DATE_FOCUS_STYLE =
  'group-focus:ring-2 group-focus:ring-slate-900 group-focus:ring-inset'

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
  const outsideMonth = !isCalendarDateInMonth(date, viewMonth)
  const isToday = isSameCalendarDate(date, academyToday)
  const orderedEvents = [...events].sort(compareEvents)
  const visibleEvents = orderedEvents.slice(0, 3)
  const remainingCount = orderedEvents.length - visibleEvents.length
  const eventCountLabel = `${orderedEvents.length} ${orderedEvents.length === 1 ? 'event' : 'events'}`
  const dateNumberStyles = isToday
    ? DATE_NUMBER_STYLES.today
    : outsideMonth
      ? DATE_NUMBER_STYLES.outsideMonth
      : DATE_NUMBER_STYLES.normal
  const mobileDateTargetStyles = `flex min-h-11 w-full min-w-0 flex-col items-center justify-center rounded-md border text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-academy focus:ring-inset sm:hidden ${dateNumberStyles} ${DATE_FOCUS_STYLE}`
  const desktopDateTargetStyles = `hidden min-h-11 min-w-11 items-center justify-center rounded-md border text-sm font-semibold sm:flex ${dateNumberStyles} ${DATE_FOCUS_STYLE}`

  function handleDateKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.target !== event.currentTarget) return
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
    const nextDate = moveCalendarFocus(
      date,
      event.key as Parameters<typeof moveCalendarFocus>[1],
    )
    const target = document.querySelector<HTMLDivElement>(
      `[data-calendar-date-focus="${calendarDateToIso(nextDate)}"]`,
    )
    if (target === null) return
    onFocusDate(nextDate)
    target.focus()
  }

  function handleDateFocus(event: FocusEvent<HTMLDivElement>) {
    if (event.target === event.currentTarget) onFocusDate(date)
  }

  return (
    <div
      role="gridcell"
      aria-label={`${dateLabel}${isToday ? ', current academy date' : ''}${orderedEvents.length > 0 ? `, ${eventCountLabel}` : ''}`}
      aria-current={isToday ? 'date' : undefined}
      className={`group min-w-0 border-b border-r border-slate-200 p-0 focus:outline-none sm:p-2 ${
        outsideMonth ? DATE_CELL_STYLES.outsideMonth : DATE_CELL_STYLES.normal
      }`}
      data-calendar-date={calendarDateToIso(date)}
      data-calendar-date-focus={calendarDateToIso(date)}
      data-date-state={isToday ? 'today' : outsideMonth ? 'outside-month' : 'normal'}
      data-outside-month={outsideMonth ? 'true' : undefined}
      onFocus={handleDateFocus}
      onKeyDown={handleDateKeyDown}
      tabIndex={isSameCalendarDate(date, focusedDate) ? 0 : -1}
    >
      {orderedEvents.length > 0 ? (
        <button
          type="button"
          aria-label={`View ${eventCountLabel} on ${dateLabel}`}
          className={mobileDateTargetStyles}
          data-calendar-compact-date={calendarDateToIso(date)}
          data-calendar-date-number={calendarDateToIso(date)}
          data-outside-month={outsideMonth ? 'true' : undefined}
          onClick={() => onSelectMore(date, orderedEvents)}
        >
          <span>{date.day}</span>
          {orderedEvents.length === 1 ? (
            <span aria-hidden="true" className="mt-0.5 size-1.5 rounded-full bg-academy" />
          ) : (
            <span className="text-[0.625rem] leading-none" aria-hidden="true">
              {orderedEvents.length}
            </span>
          )}
        </button>
      ) : (
        <span
          aria-hidden="true"
          className={mobileDateTargetStyles}
          data-calendar-compact-date={calendarDateToIso(date)}
          data-calendar-date-number={calendarDateToIso(date)}
          data-outside-month={outsideMonth ? 'true' : undefined}
        >
          {date.day}
        </span>
      )}
      <span
        aria-hidden="true"
        className={desktopDateTargetStyles}
        data-calendar-date-number={calendarDateToIso(date)}
        data-outside-month={outsideMonth ? 'true' : undefined}
      >
        {date.day}
      </span>
      <div
        className="mt-1 hidden min-w-0 space-y-0.5 sm:block"
        data-calendar-day-details={calendarDateToIso(date)}
      >
        {visibleEvents.map((event) => (
          <CalendarEventEntry key={event.occurrence_id} event={event} onSelect={onSelectEvent} />
        ))}
        {remainingCount > 0 ? (
          <button
            type="button"
            className="min-h-11 w-full rounded-md px-1 text-left text-xs font-semibold text-slate-800 underline-offset-2 hover:bg-academy/10 hover:underline focus:outline-none focus:ring-2 focus:ring-academy focus:ring-inset"
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
