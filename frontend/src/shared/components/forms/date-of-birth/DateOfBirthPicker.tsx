import { useId, useState } from 'react'
import { createPortal } from 'react-dom'
import { CalendarIcon } from '@shared/components/icons/NavIcons'
import { CALENDAR_MONTH_NAMES } from '@shared/utils/calendarDate'
import { toLongDisplayDate } from '@shared/utils/formatDate'
import DateOfBirthCalendarHeader from './DateOfBirthCalendarHeader'
import DateOfBirthDayGrid from './DateOfBirthDayGrid'
import { useDateOfBirthPicker } from './useDateOfBirthPicker'

export interface DateOfBirthPickerProps {
  id: string
  value: string
  disabled?: boolean
  error?: string
  errorId?: string
  label?: string
  placeholder?: string
  earliest?: string
  latest?: string
  clearable?: boolean
  triggerTextSize?: 'sm' | 'base'
  onChange: (value: string) => void
}

export default function DateOfBirthPicker({
  id,
  value,
  disabled = false,
  error,
  errorId,
  label = 'date of birth',
  placeholder,
  earliest,
  latest,
  clearable = false,
  triggerTextSize = 'base',
  onChange,
}: DateOfBirthPickerProps) {
  const popoverId = `${useId()}-calendar`
  const headingId = `${popoverId}-heading`
  const valueId = `${popoverId}-value`
  const [portalHost, setPortalHost] = useState<HTMLSpanElement | null>(null)
  const {
    changeByMonth,
    changeMonth,
    changeYear,
    clearDate,
    close,
    focusedDate,
    focusByDays,
    isOpen,
    open,
    popoverRef,
    position,
    range,
    selectDate,
    selectedDate,
    today,
    triggerRef,
    viewMonth,
  } = useDateOfBirthPicker({ earliest, latest, value, onChange })
  const displayValue =
    selectedDate === null
      ? (placeholder ?? `Select ${label}`)
      : toLongDisplayDate(value)

  const popover =
    isOpen && portalHost !== null
      ? createPortal(
          <div
            ref={popoverRef}
            id={popoverId}
            role="dialog"
            aria-labelledby={headingId}
            className="date-of-birth-popover fixed z-dropdown w-80 max-w-[calc(100vw-0.5rem)] overflow-y-auto rounded-lg border border-slate-300 bg-white py-2 text-slate-900"
            style={position}
          >
            <p id={headingId} className="sr-only" aria-live="polite">
              Choose {label}, {CALENDAR_MONTH_NAMES[viewMonth.month - 1]}{' '}
              {viewMonth.year}
            </p>
            <DateOfBirthCalendarHeader
              range={range}
              viewMonth={viewMonth}
              onMonthChange={changeMonth}
              onNextMonth={() => changeByMonth(1)}
              onPreviousMonth={() => changeByMonth(-1)}
              onYearChange={changeYear}
            />
            <DateOfBirthDayGrid
              focusedDate={focusedDate}
              labelledBy={headingId}
              range={range}
              selectedDate={selectedDate}
              today={today}
              viewMonth={viewMonth}
              onFocusMove={focusByDays}
              onSelect={selectDate}
            />
            {clearable && selectedDate !== null ? (
              <div className="mt-2 border-t border-slate-200 pt-1 sm:pt-2">
                <button
                  type="button"
                  aria-label={`Clear ${label}`}
                  className="flex min-h-11 w-full items-center justify-center rounded-lg px-3 text-sm font-semibold text-slate-800 hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-1"
                  onClick={clearDate}
                >
                  Clear date
                </button>
              </div>
            ) : null}
          </div>,
          portalHost,
        )
      : null

  return (
    <>
      <button
        ref={triggerRef}
        id={id}
        type="button"
        aria-controls={popoverId}
        aria-describedby={
          error !== undefined && errorId !== undefined
            ? `${valueId} ${errorId}`
            : valueId
        }
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        aria-invalid={error !== undefined}
        disabled={disabled}
        className={`mt-2 flex min-h-11 w-full items-center justify-between gap-3 rounded-lg border border-slate-300 bg-white px-3 text-left font-normal text-slate-900 hover:border-slate-400 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/40 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500 ${triggerTextSize === 'sm' ? 'text-sm' : 'text-base'}`}
        onClick={() => {
          if (isOpen) close()
          else open()
        }}
      >
        <span
          id={valueId}
          className={selectedDate === null ? 'text-slate-500' : ''}
        >
          {displayValue}
        </span>
        <CalendarIcon className="size-5 shrink-0 text-academy" />
      </button>
      <span ref={setPortalHost} />
      {popover}
    </>
  )
}
