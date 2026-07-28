export interface CalendarDate {
  year: number
  month: number
  day: number
}

export interface CalendarMonth {
  year: number
  month: number
}

export interface CalendarDateRange {
  earliest: CalendarDate
  latest: CalendarDate
}

export const CALENDAR_MONTH_NAMES = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
] as const

const ISO_CALENDAR_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/

function fromUtcDate(date: Date): CalendarDate {
  return {
    year: date.getUTCFullYear(),
    month: date.getUTCMonth() + 1,
    day: date.getUTCDate(),
  }
}

export function daysInCalendarMonth(year: number, month: number) {
  return new Date(Date.UTC(year, month, 0)).getUTCDate()
}

export function parseCalendarDate(value: string): CalendarDate | null {
  const match = ISO_CALENDAR_DATE_PATTERN.exec(value)
  if (match === null) return null

  const date = {
    year: Number(match[1]),
    month: Number(match[2]),
    day: Number(match[3]),
  }
  if (
    date.month < 1 ||
    date.month > 12 ||
    date.day < 1 ||
    date.day > daysInCalendarMonth(date.year, date.month)
  ) {
    return null
  }
  return date
}

export function calendarDateToIso(date: CalendarDate) {
  if (
    date.month < 1 ||
    date.month > 12 ||
    date.day < 1 ||
    date.day > daysInCalendarMonth(date.year, date.month)
  ) {
    throw new RangeError('Invalid calendar date')
  }
  return [
    String(date.year).padStart(4, '0'),
    String(date.month).padStart(2, '0'),
    String(date.day).padStart(2, '0'),
  ].join('-')
}

export function compareCalendarDates(
  left: CalendarDate,
  right: CalendarDate,
) {
  return calendarDateToIso(left).localeCompare(calendarDateToIso(right))
}

export function isSameCalendarDate(
  left: CalendarDate | null,
  right: CalendarDate | null,
) {
  return (
    left !== null &&
    right !== null &&
    left.year === right.year &&
    left.month === right.month &&
    left.day === right.day
  )
}

export function addCalendarDays(date: CalendarDate, amount: number) {
  return fromUtcDate(
    new Date(Date.UTC(date.year, date.month - 1, date.day + amount)),
  )
}

export function addCalendarMonths(date: CalendarDate, amount: number) {
  const firstOfTargetMonth = new Date(
    Date.UTC(date.year, date.month - 1 + amount, 1),
  )
  const year = firstOfTargetMonth.getUTCFullYear()
  const month = firstOfTargetMonth.getUTCMonth() + 1
  return {
    year,
    month,
    day: Math.min(date.day, daysInCalendarMonth(year, month)),
  }
}

export function addCalendarYears(date: CalendarDate, amount: number) {
  const year = date.year + amount
  return {
    year,
    month: date.month,
    day: Math.min(date.day, daysInCalendarMonth(year, date.month)),
  }
}

export function clampCalendarDate(
  date: CalendarDate,
  range: CalendarDateRange,
) {
  if (compareCalendarDates(date, range.earliest) < 0) return range.earliest
  if (compareCalendarDates(date, range.latest) > 0) return range.latest
  return date
}

export function calendarDateFromLocalDate(date = new Date()): CalendarDate {
  return {
    year: date.getFullYear(),
    month: date.getMonth() + 1,
    day: date.getDate(),
  }
}

export function calendarGrid(month: CalendarMonth) {
  const first = { ...month, day: 1 }
  const leadingDays = new Date(
    Date.UTC(month.year, month.month - 1, 1),
  ).getUTCDay()
  const gridStart = addCalendarDays(first, -leadingDays)
  const requiredDays = leadingDays + daysInCalendarMonth(
    month.year,
    month.month,
  )
  const cellCount = Math.ceil(requiredDays / 7) * 7
  return Array.from({ length: cellCount }, (_, index) =>
    addCalendarDays(gridStart, index),
  )
}

export function calendarMonthFromDate(date: CalendarDate): CalendarMonth {
  return { year: date.year, month: date.month }
}

export function compareCalendarMonths(
  left: CalendarMonth,
  right: CalendarMonth,
) {
  return left.year === right.year
    ? left.month - right.month
    : left.year - right.year
}

export function calendarDateForFormatting(date: CalendarDate) {
  return new Date(Date.UTC(date.year, date.month - 1, date.day))
}
