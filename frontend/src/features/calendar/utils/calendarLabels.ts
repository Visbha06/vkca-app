import type { AgeGroup, CalendarEventInstance, EventType, ScopeKind } from '../types/calendar'

const EVENT_TYPE_LABELS: Record<EventType, string> = {
  practice: 'Practice',
  game: 'Game',
  miscellaneous: 'Miscellaneous',
}

const AGE_GROUP_LABELS: Record<AgeGroup, string> = {
  J: 'Juniors',
  U11: 'U11',
  U13: 'U13',
  U15: 'U15',
}

export function getEventTypeLabel(eventType: EventType) {
  return EVENT_TYPE_LABELS[eventType]
}

export function getAgeGroupLabel(ageGroup: AgeGroup) {
  return AGE_GROUP_LABELS[ageGroup]
}

export function getScopeLabel(
  scopeKind: ScopeKind,
  ageGroups: AgeGroup[],
) {
  if (scopeKind === 'all_academy') return 'All Academy'
  return ageGroups.map(getAgeGroupLabel).join(', ')
}

export function formatEventTime(
  startTime: string | null,
  endTime: string | null,
) {
  if (startTime === null || endTime === null) return 'All day'
  return `${formatClockTime(startTime)}–${formatClockTime(endTime)}`
}

function formatClockTime(value: string) {
  const [hourText, minuteText] = value.split(':')
  const hour = Number(hourText)
  const minute = Number(minuteText)
  if (!Number.isInteger(hour) || !Number.isInteger(minute)) return value
  const period = hour >= 12 ? 'PM' : 'AM'
  const twelveHour = hour % 12 || 12
  return `${twelveHour}:${String(minute).padStart(2, '0')} ${period}`
}

export function getEventAccessibleLabel(event: CalendarEventInstance) {
  const recurrence = event.is_recurring
    ? `, recurring${event.recurrence_summary === null ? '' : `, ${event.recurrence_summary}`}`
    : ''
  return `${getEventTypeLabel(event.event_type)} event: ${event.name}, ${formatEventTime(event.start_time, event.end_time)}, ${getScopeLabel(event.scope_kind, event.age_groups)}${recurrence}`
}
