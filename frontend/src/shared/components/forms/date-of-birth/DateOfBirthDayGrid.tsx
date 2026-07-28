import type { KeyboardEvent } from 'react'
import {
  calendarDateForFormatting,
  calendarDateToIso,
  calendarGrid,
  compareCalendarDates,
  isSameCalendarDate,
  type CalendarDate,
  type CalendarDateRange,
  type CalendarMonth,
} from '@shared/utils/calendarDate'

const WEEKDAYS = [
  ['Su', 'Sunday'],
  ['Mo', 'Monday'],
  ['Tu', 'Tuesday'],
  ['We', 'Wednesday'],
  ['Th', 'Thursday'],
  ['Fr', 'Friday'],
  ['Sa', 'Saturday'],
] as const

const accessibleDateFormatter = new Intl.DateTimeFormat('en-US', {
  weekday: 'long',
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  timeZone: 'UTC',
})

interface DateOfBirthDayGridProps {
  focusedDate: CalendarDate
  range: CalendarDateRange
  selectedDate: CalendarDate | null
  today: CalendarDate
  viewMonth: CalendarMonth
  labelledBy: string
  onFocusMove: (days: number) => void
  onSelect: (date: CalendarDate) => void
}

function dayClass(
  selected: boolean,
  today: boolean,
  outsideMonth: boolean,
) {
  return [
    'flex h-11 w-11 justify-self-center items-center justify-center rounded-lg border text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-inset',
    selected
      ? 'border-academy bg-academy font-bold text-slate-950 focus-visible:ring-slate-900'
      : `border-transparent bg-transparent ${
          outsideMonth ? 'text-slate-500' : 'text-slate-900'
        } enabled:hover:bg-academy/10 focus-visible:ring-academy`,
    today && !selected ? 'border-slate-500 font-bold' : '',
    'disabled:cursor-not-allowed disabled:bg-transparent disabled:text-slate-400',
  ].join(' ')
}

export default function DateOfBirthDayGrid({
  focusedDate,
  range,
  selectedDate,
  today,
  viewMonth,
  labelledBy,
  onFocusMove,
  onSelect,
}: DateOfBirthDayGridProps) {
  const days = calendarGrid(viewMonth)
  const weekCount = days.length / 7

  function handleKeyDown(
    event: KeyboardEvent<HTMLButtonElement>,
    date: CalendarDate,
  ) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelect(date)
      return
    }
    const movement = {
      ArrowLeft: -1,
      ArrowRight: 1,
      ArrowUp: -7,
      ArrowDown: 7,
    }[event.key]
    if (movement === undefined) return
    event.preventDefault()
    onFocusMove(movement)
  }

  return (
    <div
      role="grid"
      aria-labelledby={labelledBy}
      className="mt-2"
    >
      <div role="row" className="grid grid-cols-7 gap-px">
        {WEEKDAYS.map(([shortName, fullName]) => (
          <div
            key={fullName}
            role="columnheader"
            aria-label={fullName}
            className="flex h-8 items-center justify-center text-xs font-semibold text-slate-600"
          >
            <span aria-hidden="true">{shortName}</span>
          </div>
        ))}
      </div>
      {Array.from({ length: weekCount }, (_, weekIndex) => (
        <div
          key={weekIndex}
          role="row"
          data-calendar-week={weekIndex + 1}
          className="grid grid-cols-7 gap-px"
        >
          {days.slice(weekIndex * 7, weekIndex * 7 + 7).map((date) => {
            const isoDate = calendarDateToIso(date)
            const selected = isSameCalendarDate(date, selectedDate)
            const isToday = isSameCalendarDate(date, today)
            const outsideMonth =
              date.year !== viewMonth.year || date.month !== viewMonth.month
            const unavailable =
              compareCalendarDates(date, range.earliest) < 0 ||
              compareCalendarDates(date, range.latest) > 0
            const accessibleDate = accessibleDateFormatter.format(
              calendarDateForFormatting(date),
            )

            return (
              <button
                key={isoDate}
                type="button"
                role="gridcell"
                aria-current={isToday ? 'date' : undefined}
                aria-disabled={unavailable || undefined}
                aria-label={isToday ? `Today, ${accessibleDate}` : accessibleDate}
                aria-selected={selected}
                data-calendar-date={isoDate}
                data-outside-month={outsideMonth || undefined}
                disabled={unavailable}
                tabIndex={isSameCalendarDate(date, focusedDate) ? 0 : -1}
                className={dayClass(selected, isToday, outsideMonth)}
                onClick={() => onSelect(date)}
                onKeyDown={(event) => handleKeyDown(event, date)}
              >
                {date.day}
              </button>
            )
          })}
        </div>
      ))}
    </div>
  )
}
