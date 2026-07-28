import type {
  CalendarDateRange,
  CalendarMonth,
} from '@shared/utils/calendarDate'
import {
  CALENDAR_MONTH_NAMES,
  compareCalendarMonths,
} from '@shared/utils/calendarDate'

interface DateOfBirthCalendarHeaderProps {
  range: CalendarDateRange
  viewMonth: CalendarMonth
  onMonthChange: (month: number) => void
  onNextMonth: () => void
  onPreviousMonth: () => void
  onYearChange: (year: number) => void
}

function MonthChevron({ direction }: { direction: 'left' | 'right' }) {
  return (
    <svg
      aria-hidden="true"
      className="size-5"
      fill="none"
      viewBox="0 0 24 24"
    >
      <path
        d={direction === 'left' ? 'm15 18-6-6 6-6' : 'm9 6 6 6-6 6'}
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
      />
    </svg>
  )
}

const selectClass =
  'min-h-11 min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-2 text-sm font-semibold text-slate-900 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/40'

export default function DateOfBirthCalendarHeader({
  range,
  viewMonth,
  onMonthChange,
  onNextMonth,
  onPreviousMonth,
  onYearChange,
}: DateOfBirthCalendarHeaderProps) {
  const earliestMonth = {
    year: range.earliest.year,
    month: range.earliest.month,
  }
  const latestMonth = {
    year: range.latest.year,
    month: range.latest.month,
  }
  const years = Array.from(
    { length: range.latest.year - range.earliest.year + 1 },
    (_, index) => range.earliest.year + index,
  )

  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        aria-label="Previous month"
        disabled={compareCalendarMonths(viewMonth, earliestMonth) <= 0}
        className="flex size-11 shrink-0 items-center justify-center rounded-lg text-slate-700 hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-1 disabled:cursor-not-allowed disabled:text-slate-400"
        onClick={onPreviousMonth}
      >
        <MonthChevron direction="left" />
      </button>
      <div className="flex min-w-0 flex-1 gap-1">
        <select
          aria-label="Month"
          className={selectClass}
          value={viewMonth.month}
          onChange={(event) => onMonthChange(Number(event.target.value))}
        >
          {CALENDAR_MONTH_NAMES.map((name, index) => {
            const month = index + 1
            const outsideRange =
              (viewMonth.year === range.earliest.year &&
                month < range.earliest.month) ||
              (viewMonth.year === range.latest.year &&
                month > range.latest.month)
            return (
              <option key={name} value={month} disabled={outsideRange}>
                {name}
              </option>
            )
          })}
        </select>
        <select
          aria-label="Year"
          className={selectClass}
          value={viewMonth.year}
          onChange={(event) => onYearChange(Number(event.target.value))}
        >
          {years.map((year) => (
            <option key={year} value={year}>
              {year}
            </option>
          ))}
        </select>
      </div>
      <button
        type="button"
        aria-label="Next month"
        disabled={compareCalendarMonths(viewMonth, latestMonth) >= 0}
        className="flex size-11 shrink-0 items-center justify-center rounded-lg text-slate-700 hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-1 disabled:cursor-not-allowed disabled:text-slate-400"
        onClick={onNextMonth}
      >
        <MonthChevron direction="right" />
      </button>
    </div>
  )
}
