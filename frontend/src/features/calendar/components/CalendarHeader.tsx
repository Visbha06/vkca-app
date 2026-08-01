import {
  CALENDAR_MONTH_NAMES,
  calendarDateForFormatting,
  calendarYearOptions,
  parseAcademyDate,
  type CalendarMonth,
} from '@shared/utils/calendarDate'

interface CalendarHeaderProps {
  viewMonth: CalendarMonth
  academyToday: string
  isLoading: boolean
  onPreviousMonth: () => void
  onNextMonth: () => void
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

export default function CalendarHeader({
  viewMonth,
  academyToday,
  isLoading,
  onPreviousMonth,
  onNextMonth,
  onYearChange,
}: CalendarHeaderProps) {
  const parsedToday = parseAcademyDate(academyToday)
  const years = calendarYearOptions(
    parsedToday ?? { year: 2026, month: 1, day: 1 },
  )
  const monthLabel = new Intl.DateTimeFormat('en-US', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(calendarDateForFormatting({ ...viewMonth, day: 1 }))
  const isHistorical = viewMonth.year < years[0]

  return (
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div className="min-w-0">
        <p className="text-sm font-semibold text-slate-600">Academy calendar</p>
        <h2 className="mt-1 text-xl font-bold text-slate-900" id="calendar-month-heading">
          {monthLabel}
        </h2>
        {isHistorical ? (
          <p className="mt-1 text-sm text-slate-600">Viewing historical year {viewMonth.year}</p>
        ) : null}
      </div>
      <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
        {isHistorical ? null : (
          <label className="flex min-h-11 items-center gap-2 text-sm font-semibold text-slate-700">
            <span className="sr-only">Calendar year</span>
            <select
              aria-label="Calendar year"
              className="min-h-11 min-w-0 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-900 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/40"
              disabled={isLoading}
              value={viewMonth.year}
              onChange={(event) => onYearChange(Number(event.target.value))}
            >
              {years.map((year) => (
                <option key={year} value={year}>{year}</option>
              ))}
            </select>
          </label>
        )}
        <button
          type="button"
          aria-label="Previous month"
          className="flex min-h-11 min-w-11 items-center justify-center rounded-lg border border-slate-300 bg-white text-slate-800 hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-1 disabled:cursor-not-allowed disabled:text-slate-400"
          disabled={isLoading}
          onClick={onPreviousMonth}
        >
          <MonthChevron direction="left" />
        </button>
        <button
          type="button"
          aria-label="Next month"
          className="flex min-h-11 min-w-11 items-center justify-center rounded-lg border border-slate-300 bg-white text-slate-800 hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-1 disabled:cursor-not-allowed disabled:text-slate-400"
          disabled={isLoading}
          onClick={onNextMonth}
        >
          <MonthChevron direction="right" />
        </button>
      </div>
      <p className="sr-only" role="status" aria-live="polite">
        {isLoading ? `Loading ${monthLabel}` : `${monthLabel} ready`}
      </p>
      <span className="sr-only">{CALENDAR_MONTH_NAMES[viewMonth.month - 1]}</span>
    </header>
  )
}
