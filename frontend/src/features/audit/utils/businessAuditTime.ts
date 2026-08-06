export const BUSINESS_AUDIT_TIME_ZONE = 'America/Los_Angeles'

interface AcademyDateParts {
  year: number
  month: number
  day: number
}

function parseInstant(value: string | Date) {
  const instant = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(instant.getTime())) {
    throw new RangeError('Business audit timestamp must be a valid ISO instant')
  }
  return instant
}

function academyDateParts(instant: Date): AcademyDateParts {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: BUSINESS_AUDIT_TIME_ZONE,
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
  }).formatToParts(instant)
  const values = new Map(parts.map((part) => [part.type, part.value]))
  return {
    year: Number(values.get('year')),
    month: Number(values.get('month')),
    day: Number(values.get('day')),
  }
}

function academyDateDistance(later: Date, earlier: Date) {
  const laterParts = academyDateParts(later)
  const earlierParts = academyDateParts(earlier)
  return Math.round(
    (Date.UTC(laterParts.year, laterParts.month - 1, laterParts.day) -
      Date.UTC(earlierParts.year, earlierParts.month - 1, earlierParts.day)) /
      86_400_000,
  )
}

function capitalize(value: string) {
  return value.length === 0 ? value : `${value[0].toUpperCase()}${value.slice(1)}`
}

export function formatBusinessAuditTimestamp(
  timestamp: string,
  locale = 'en-US',
) {
  return new Intl.DateTimeFormat(locale, {
    timeZone: BUSINESS_AUDIT_TIME_ZONE,
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parseInstant(timestamp))
}

export function formatBusinessAuditRelativeTime(
  timestamp: string,
  now: string | Date = new Date(),
  locale = 'en-US',
) {
  const eventTime = parseInstant(timestamp)
  const currentTime = parseInstant(now)
  const formatter = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' })
  const academyDays = academyDateDistance(currentTime, eventTime)

  if (academyDays !== 0) {
    return capitalize(formatter.format(-academyDays, 'day'))
  }

  const elapsedSeconds = Math.round(
    (currentTime.getTime() - eventTime.getTime()) / 1000,
  )
  const absoluteSeconds = Math.abs(elapsedSeconds)
  if (absoluteSeconds < 60) return 'Just now'
  if (absoluteSeconds < 3_600) {
    return formatter.format(-Math.round(elapsedSeconds / 60), 'minute')
  }
  return formatter.format(-Math.round(elapsedSeconds / 3_600), 'hour')
}
