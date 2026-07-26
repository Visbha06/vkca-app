const API_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/
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
  const match = API_DATE_PATTERN.exec(apiDate)
  if (match === null) throw new RangeError('Invalid API date')

  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  const parsed = new Date(0)
  parsed.setUTCHours(0, 0, 0, 0)
  parsed.setUTCFullYear(year, month - 1, day)

  if (
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== day
  ) {
    throw new RangeError('Invalid API date')
  }

  return { year, month, day }
}

export function toDisplayDate(apiDate: string) {
  const { year, month, day } = readApiDate(apiDate)
  return `${String(day).padStart(2, '0')} ${MONTH_LABELS[month - 1]} ${year}`
}

export function toApiDate(date: Date) {
  if (Number.isNaN(date.getTime())) throw new RangeError('Invalid date')

  const year = String(date.getUTCFullYear()).padStart(4, '0')
  const month = String(date.getUTCMonth() + 1).padStart(2, '0')
  const day = String(date.getUTCDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}
