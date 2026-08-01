import { useMemo } from 'react'
import {
  calendarDateForFormatting,
  calendarGridRows,
  type CalendarDate,
  type CalendarMonth,
} from '@shared/utils/calendarDate'
import type { CalendarEventInstance } from '../types/calendar'
import CalendarDayCell from './CalendarDayCell'

const WEEKDAYS = [
  ['Sunday', 'Sun'],
  ['Monday', 'Mon'],
  ['Tuesday', 'Tue'],
  ['Wednesday', 'Wed'],
  ['Thursday', 'Thu'],
  ['Friday', 'Fri'],
  ['Saturday', 'Sat'],
] as const

interface CalendarMonthGridProps {
  viewMonth: CalendarMonth
  academyToday: string | null
  events: CalendarEventInstance[]
  focusedDate: CalendarDate
  isLoading?: boolean
  onFocusDate: (date: CalendarDate) => void
  onSelectEvent: (event: CalendarEventInstance) => void
  onSelectMore: (date: CalendarDate, events: CalendarEventInstance[]) => void
}

export default function CalendarMonthGrid({
  viewMonth,
  academyToday,
  events,
  focusedDate,
  isLoading = false,
  onFocusDate,
  onSelectEvent,
  onSelectMore,
}: CalendarMonthGridProps) {
  const rows = calendarGridRows(viewMonth)
  const todayDate = academyToday === null ? null : parseDate(academyToday)
  const eventsByDate = useMemo(() => {
    const grouped = new Map<string, CalendarEventInstance[]>()
    for (const event of events) {
      const existing = grouped.get(event.event_date) ?? []
      existing.push(event)
      grouped.set(event.event_date, existing)
    }
    return grouped
  }, [events])
  const monthLabel = new Intl.DateTimeFormat('en-US', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(calendarDateForFormatting({ ...viewMonth, day: 1 }))

  return (
    <div
      role="grid"
      aria-label={`${monthLabel} calendar`}
      aria-busy={isLoading}
      className="min-w-0 overflow-hidden rounded-lg border border-slate-200 bg-white"
    >
      <div role="row" className="grid grid-cols-7 border-b border-slate-200 bg-slate-50">
        {WEEKDAYS.map(([fullName, shortName]) => (
          <div
            key={fullName}
            role="columnheader"
            aria-label={fullName}
            className="flex min-h-11 items-center justify-center border-r border-slate-200 px-1 text-xs font-semibold text-slate-600 last:border-r-0 sm:text-sm"
          >
            <span aria-hidden="true">{shortName}</span>
          </div>
        ))}
      </div>
      {rows.map((row, rowIndex) => (
        <div key={rowIndex} role="row" className="grid grid-cols-7">
          {row.map((date) => (
            <CalendarDayCell
              key={`${date.year}-${date.month}-${date.day}`}
              date={date}
              viewMonth={viewMonth}
              academyToday={todayDate}
              focusedDate={focusedDate}
              events={eventsByDate.get(toIso(date)) ?? []}
              onFocusDate={onFocusDate}
              onSelectEvent={onSelectEvent}
              onSelectMore={onSelectMore}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

function parseDate(value: string): CalendarDate | null {
  const [year, month, day] = value.split('-').map(Number)
  if (![year, month, day].every(Number.isInteger)) return null
  return { year, month, day }
}

function toIso(date: CalendarDate) {
  return `${String(date.year).padStart(4, '0')}-${String(date.month).padStart(2, '0')}-${String(date.day).padStart(2, '0')}`
}
