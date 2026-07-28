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
  onChange: (value: string) => void
}

export default function DateOfBirthPicker({
  id,
  value,
  disabled = false,
  error,
  errorId,
  onChange,
}: DateOfBirthPickerProps) {
  const popoverId = `${useId()}-date-of-birth-calendar`
  const headingId = `${popoverId}-heading`
  const valueId = `${popoverId}-value`
  const [portalHost, setPortalHost] = useState<HTMLSpanElement | null>(null)
  const {
    changeByMonth,
    changeMonth,
    changeYear,
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
  } = useDateOfBirthPicker({ value, onChange })
  const displayValue =
    selectedDate === null
      ? 'Select date of birth'
      : toLongDisplayDate(value)

  const popover =
    isOpen && portalHost !== null
      ? createPortal(
          <div
            ref={popoverRef}
            id={popoverId}
            role="dialog"
            aria-labelledby={headingId}
            className="date-of-birth-popover fixed z-dropdown w-80 max-w-full overflow-y-auto rounded-lg border border-slate-300 bg-white p-0.5 text-slate-900 sm:p-2"
            style={position}
          >
            <p id={headingId} className="sr-only" aria-live="polite">
              Choose date of birth, {CALENDAR_MONTH_NAMES[viewMonth.month - 1]}{' '}
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
        className="mt-2 flex min-h-11 w-full items-center justify-between gap-3 rounded-lg border border-slate-300 bg-white px-3 text-left text-base text-slate-900 hover:border-slate-400 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/40 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500"
        onClick={isOpen ? close : open}
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
