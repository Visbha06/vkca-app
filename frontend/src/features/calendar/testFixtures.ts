import type { CalendarDate } from '@shared/utils/calendarDate'

export const ACADEMY_TIMEZONE = 'America/Los_Angeles' as const
export const ACADEMY_REFERENCE_DATE: CalendarDate = {
  year: 2026,
  month: 8,
  day: 1,
}
export const ACADEMY_REFERENCE_TIME = '12:00' as const

export type CalendarFixtureScope = {
  scope_kind: 'age_group' | 'all_academy'
  age_groups: string[]
}

export type CalendarFixtureEvent = {
  name: string
  event_type: 'practice' | 'game' | 'miscellaneous'
  event_date: CalendarDate
  start_time: string | null
  end_time: string | null
  scope: CalendarFixtureScope
}

export function buildCalendarFixtureScope(
  scopeKind: CalendarFixtureScope['scope_kind'] = 'age_group',
  ageGroups = ['U13'],
): CalendarFixtureScope {
  return {
    scope_kind: scopeKind,
    age_groups: scopeKind === 'all_academy' ? [] : [...ageGroups],
  }
}

export function buildCalendarFixtureEvent(
  overrides: Partial<CalendarFixtureEvent> = {},
): CalendarFixtureEvent {
  return {
    name: 'U13 Wednesday Practice',
    event_type: 'practice',
    event_date: { ...ACADEMY_REFERENCE_DATE },
    start_time: '17:00',
    end_time: '18:30',
    scope: buildCalendarFixtureScope(),
    ...overrides,
  }
}
