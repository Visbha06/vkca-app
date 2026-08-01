export type AcademyDate = string
export type AcademyTime = string

export type AgeGroup = 'J' | 'U11' | 'U13' | 'U15'

export type EventType = 'practice' | 'game' | 'miscellaneous'

export type ScopeKind = 'age_group' | 'all_academy'

export type RecurrenceFrequency = 'weekly' | 'yearly'

export type RecurrenceTermination =
  | 'never'
  | 'end_date'
  | 'occurrence_count'

export interface CalendarScope {
  scope_kind: ScopeKind
  age_groups: AgeGroup[]
}

export interface CalendarRecurrence {
  frequency: RecurrenceFrequency
  termination: RecurrenceTermination
  end_date: AcademyDate | null
  occurrence_count: number | null
}

export interface RecurrenceSeriesResponse extends CalendarRecurrence {
  id: string
  event_id: string
  weekday: number | null
  month: number | null
  month_day: number | null
  created_at: string
  updated_at: string
}

export interface CalendarEventValues {
  event_type: EventType
  name: string
  event_date: AcademyDate
  is_all_day: boolean
  start_time: AcademyTime | null
  end_time: AcademyTime | null
  scope: CalendarScope
}

export interface CalendarEventCreatePayload extends CalendarEventValues {
  recurrence: CalendarRecurrence | null
}

export interface OwningEventVersionPayload {
  version_number: number
}

export interface CalendarStandaloneUpdatePayload
  extends CalendarEventValues,
    OwningEventVersionPayload {}

export interface CalendarOccurrenceUpdatePayload
  extends CalendarEventValues,
    OwningEventVersionPayload {
  exception_version_number: number | null
}

export interface CalendarSeriesUpdatePayload
  extends CalendarEventValues,
    OwningEventVersionPayload {
  recurrence: CalendarRecurrence
  confirm_exception_removals: boolean
}

export type CalendarEventDeletePayload = OwningEventVersionPayload

export interface CalendarOccurrenceDeletePayload
  extends OwningEventVersionPayload {
  exception_version_number: number | null
}

export interface CalendarEventDefinitionResponse
  extends CalendarEventValues,
    OwningEventVersionPayload {
  id: string
  recurrence: RecurrenceSeriesResponse | null
  created_at: string
  updated_at: string
}

export interface CalendarEventInstance {
  occurrence_id: string
  event_id: string
  series_id: string | null
  original_date: AcademyDate
  event_date: AcademyDate
  event_type: EventType
  name: string
  is_all_day: boolean
  start_time: AcademyTime | null
  end_time: AcademyTime | null
  scope_kind: ScopeKind
  age_groups: AgeGroup[]
  is_recurring: boolean
  recurrence_summary: string | null
  event_version_number: number
  exception_id: string | null
  exception_version_number: number | null
}

export interface CalendarRangeResponse {
  academy_today: AcademyDate
  start_date: AcademyDate
  end_date: AcademyDate
  events: CalendarEventInstance[]
}

export interface CalendarTodayResponse {
  academy_today: AcademyDate
  events: CalendarEventInstance[]
}

export type CalendarErrorCode =
  | 'calendar_range_too_large'
  | 'calendar_event_in_past'
  | 'calendar_event_times_invalid'
  | 'calendar_scope_invalid'
  | 'calendar_recurrence_invalid'
  | 'exception_removal_confirmation_required'
  | 'calendar_stale_version'

export interface CalendarApiError {
  detail: string
  code: CalendarErrorCode | null
}

export interface ExceptionRemovalWarningResponse {
  detail: string
  code: 'exception_removal_confirmation_required'
  removed_exception_original_dates: AcademyDate[]
}
