import type {
  AcademyDate,
  CalendarEventCreatePayload,
  CalendarEventInstance,
  CalendarRecurrence,
} from '../types/calendar'

export interface CalendarFormErrors {
  name?: string
  event_date?: string
  times?: string
  scope?: string
  recurrence?: string
  recurrence_end_date?: string
  occurrence_count?: string
}

export function emptyCalendarForm(
  academyToday: AcademyDate,
): CalendarEventCreatePayload {
  return {
    event_type: 'practice',
    name: '',
    event_date: academyToday,
    is_all_day: false,
    start_time: '17:00',
    end_time: '18:30',
    scope: { scope_kind: 'age_group', age_groups: ['U13'] },
    recurrence: null,
  }
}

function fallbackRecurrence(event: CalendarEventInstance): CalendarRecurrence {
  return {
    frequency: event.recurrence_summary?.toLowerCase().includes('year')
      ? 'yearly'
      : 'weekly',
    termination: 'never',
    end_date: null,
    occurrence_count: null,
  }
}

export function calendarEventToForm(
  event: CalendarEventInstance,
  target: 'occurrence' | 'series' = 'occurrence',
): CalendarEventCreatePayload {
  const definition = target === 'series' ? event.series_definition : null
  const recurrence = definition?.recurrence
  return {
    event_type: definition?.event_type ?? event.event_type,
    name: definition?.name ?? event.name,
    event_date: definition?.event_date ?? event.event_date,
    is_all_day: definition?.is_all_day ?? event.is_all_day,
    start_time: (definition?.start_time ?? event.start_time)?.slice(0, 5) ?? null,
    end_time: (definition?.end_time ?? event.end_time)?.slice(0, 5) ?? null,
    scope: definition?.scope
      ? {
          scope_kind: definition.scope.scope_kind,
          age_groups: [...definition.scope.age_groups],
        }
      : {
          scope_kind: event.scope_kind,
          age_groups: [...event.age_groups],
        },
    recurrence: event.is_recurring
      ? {
          frequency: recurrence?.frequency ?? fallbackRecurrence(event).frequency,
          termination:
            recurrence?.termination ?? fallbackRecurrence(event).termination,
          end_date: recurrence?.end_date ?? null,
          occurrence_count: recurrence?.occurrence_count ?? null,
        }
      : null,
  }
}

export function validateCalendarForm(
  values: CalendarEventCreatePayload,
  academyToday: AcademyDate,
  allowRecurrence: boolean,
  unchangedPastValues?: CalendarEventCreatePayload,
): CalendarFormErrors {
  const errors: CalendarFormErrors = {}
  if (values.name.trim().length === 0) errors.name = 'Enter an event name.'
  const keepsHistoricalSchedule =
    unchangedPastValues !== undefined &&
    values.event_date === unchangedPastValues.event_date &&
    values.is_all_day === unchangedPastValues.is_all_day &&
    values.start_time === unchangedPastValues.start_time &&
    values.end_time === unchangedPastValues.end_time
  if (!/^\d{4}-\d{2}-\d{2}$/.test(values.event_date)) {
    errors.event_date = 'Enter a valid academy date.'
  } else if (values.event_date < academyToday && !keepsHistoricalSchedule) {
    errors.event_date = 'Choose an academy date that has not passed.'
  }

  if (values.is_all_day && values.event_type !== 'miscellaneous') {
    errors.times = 'Only Miscellaneous events can be all day.'
  } else if (
    !values.is_all_day &&
    (values.start_time === null ||
      values.end_time === null ||
      values.start_time >= values.end_time)
  ) {
    errors.times = 'Enter a start time and a later end time.'
  }

  if (
    values.scope.scope_kind === 'age_group' &&
    values.scope.age_groups.length === 0
  ) {
    errors.scope = 'Select at least one age group or choose All Academy.'
  }

  if (allowRecurrence && values.recurrence !== null) {
    if (
      values.recurrence.termination === 'end_date' &&
      (values.recurrence.end_date === null ||
        values.recurrence.end_date < values.event_date)
    ) {
      errors.recurrence_end_date =
        'Choose an end date on or after the first event.'
    }
    if (
      values.recurrence.termination === 'occurrence_count' &&
      (values.recurrence.occurrence_count === null ||
        !Number.isInteger(values.recurrence.occurrence_count) ||
        values.recurrence.occurrence_count < 1)
    ) {
      errors.occurrence_count = 'Enter at least one occurrence.'
    }
  }
  return errors
}

export function normalizeCalendarForm(
  values: CalendarEventCreatePayload,
  allowRecurrence: boolean,
): CalendarEventCreatePayload {
  return {
    ...values,
    name: values.name.trim(),
    start_time: values.is_all_day ? null : values.start_time,
    end_time: values.is_all_day ? null : values.end_time,
    recurrence: allowRecurrence ? values.recurrence : null,
  }
}
