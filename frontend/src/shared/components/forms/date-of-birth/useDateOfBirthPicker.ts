import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import {
  addCalendarDays,
  addCalendarMonths,
  addCalendarYears,
  calendarDateFromLocalDate,
  calendarDateToIso,
  calendarMonthFromDate,
  clampCalendarDate,
  daysInCalendarMonth,
  parseCalendarDate,
  type CalendarDate,
  type CalendarMonth,
} from '@shared/utils/calendarDate'
import { useAnchoredPopoverPosition } from './useAnchoredPopoverPosition'

const DATE_OF_BIRTH_YEAR_SPAN = 100

interface UseDateOfBirthPickerOptions {
  earliest?: string
  latest?: string
  value: string
  onChange: (value: string) => void
}

export function useDateOfBirthPicker({
  earliest,
  latest,
  value,
  onChange,
}: UseDateOfBirthPickerOptions) {
  const today = useMemo(() => calendarDateFromLocalDate(), [])
  const range = useMemo(
    () => {
      const defaultEarliest = addCalendarYears(
        today,
        -DATE_OF_BIRTH_YEAR_SPAN,
      )
      return {
        earliest: parseCalendarDate(earliest ?? '') ?? defaultEarliest,
        latest: parseCalendarDate(latest ?? '') ?? today,
      }
    },
    [earliest, latest, today],
  )
  const selectedDate = parseCalendarDate(value)
  const initialDate = clampCalendarDate(selectedDate ?? today, range)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const pendingDayFocus = useRef(false)
  const [isOpen, setIsOpen] = useState(false)
  const [focusedDate, setFocusedDate] = useState(initialDate)
  const [viewMonth, setViewMonth] = useState<CalendarMonth>(
    calendarMonthFromDate(initialDate),
  )
  const position = useAnchoredPopoverPosition({
    isOpen,
    layoutKey: `${viewMonth.year}-${viewMonth.month}`,
    popoverRef,
    triggerRef,
  })

  const close = useCallback((restoreTriggerFocus = false) => {
    setIsOpen(false)
    if (restoreTriggerFocus) {
      window.setTimeout(() => triggerRef.current?.focus(), 0)
    }
  }, [])

  function open() {
    const openingDate = clampCalendarDate(selectedDate ?? today, range)
    setFocusedDate(openingDate)
    setViewMonth(calendarMonthFromDate(openingDate))
    pendingDayFocus.current = true
    setIsOpen(true)
  }

  function selectDate(date: CalendarDate) {
    onChange(calendarDateToIso(date))
    close(true)
  }

  function clearDate() {
    onChange('')
    close(true)
  }

  function focusByDays(days: number) {
    const nextDate = clampCalendarDate(
      addCalendarDays(focusedDate, days),
      range,
    )
    setFocusedDate(nextDate)
    setViewMonth(calendarMonthFromDate(nextDate))
    pendingDayFocus.current = true
  }

  function changeView(nextView: CalendarMonth) {
    const minimumMonth =
      nextView.year === range.earliest.year ? range.earliest.month : 1
    const maximumMonth =
      nextView.year === range.latest.year ? range.latest.month : 12
    const month = Math.min(Math.max(nextView.month, minimumMonth), maximumMonth)
    const nextDate = clampCalendarDate(
      {
        year: nextView.year,
        month,
        day: Math.min(
          focusedDate.day,
          daysInCalendarMonth(nextView.year, month),
        ),
      },
      range,
    )
    setViewMonth({ year: nextDate.year, month: nextDate.month })
    setFocusedDate(nextDate)
  }

  function changeMonth(month: number) {
    changeView({ year: viewMonth.year, month })
  }

  function changeYear(year: number) {
    changeView({ year, month: viewMonth.month })
  }

  function changeByMonth(months: number) {
    const nextDate = clampCalendarDate(
      addCalendarMonths(focusedDate, months),
      range,
    )
    setFocusedDate(nextDate)
    setViewMonth(calendarMonthFromDate(nextDate))
  }

  useLayoutEffect(() => {
    if (!isOpen || !pendingDayFocus.current) return
    pendingDayFocus.current = false
    popoverRef.current
      ?.querySelector<HTMLElement>(
        `[data-calendar-date="${calendarDateToIso(focusedDate)}"]`,
      )
      ?.focus()
  }, [focusedDate, isOpen, viewMonth])

  useEffect(() => {
    if (!isOpen) return

    function handlePointerDown(event: PointerEvent) {
      const target = event.target
      if (
        target instanceof Node &&
        !popoverRef.current?.contains(target) &&
        !triggerRef.current?.contains(target)
      ) {
        close()
      }
    }

    function handleFocusIn(event: FocusEvent) {
      const target = event.target
      if (
        target instanceof Node &&
        !popoverRef.current?.contains(target) &&
        !triggerRef.current?.contains(target)
      ) {
        close()
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key !== 'Escape') return
      event.preventDefault()
      event.stopImmediatePropagation()
      close(true)
    }

    document.addEventListener('pointerdown', handlePointerDown, true)
    document.addEventListener('focusin', handleFocusIn, true)
    document.addEventListener('keydown', handleEscape, true)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown, true)
      document.removeEventListener('focusin', handleFocusIn, true)
      document.removeEventListener('keydown', handleEscape, true)
    }
  }, [close, isOpen])

  return {
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
  }
}
