import {
  calendarDateForFormatting,
  parseCalendarDate,
} from './calendarDate'

const MONTH_LABELS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
] as const

function readApiDate(apiDate: string) {
  const date = parseCalendarDate(apiDate)
  if (date === null) throw new RangeError('Invalid API date')
  return date
}

export function toDisplayDate(apiDate: string) {
  const { year, month, day } = readApiDate(apiDate)
  return `${String(day).padStart(2, '0')} ${MONTH_LABELS[month - 1]} ${year}`
}

export function toLongDisplayDate(apiDate: string) {
  const date = readApiDate(apiDate)
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone: 'UTC',
  }).format(calendarDateForFormatting(date))
}

export function toApiDate(date: Date) {
  if (Number.isNaN(date.getTime())) throw new RangeError('Invalid date')

  const year = String(date.getUTCFullYear()).padStart(4, '0')
  const month = String(date.getUTCMonth() + 1).padStart(2, '0')
  const day = String(date.getUTCDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}
