import type { Page } from '@playwright/test'
import type {
  AcademyDate,
  CalendarEventCreatePayload,
  CalendarEventDefinitionResponse,
  CalendarEventInstance,
  CalendarOccurrenceDeletePayload,
  CalendarOccurrenceUpdatePayload,
  CalendarSeriesUpdatePayload,
} from '@features/calendar/types/calendar'

const academyToday = '2026-08-05'
const timestamp = '2026-08-01T12:00:00Z'
const eventId = '22222222-2222-4222-8222-222222222222'
const seriesId = '11111111-1111-4111-8111-111111111111'

interface MockException {
  values: Omit<CalendarOccurrenceUpdatePayload, 'version_number' | 'exception_version_number'>
  version: number
  deleted: boolean
}

export interface CalendarApiState {
  createPayloads: CalendarEventCreatePayload[]
  definition: CalendarEventDefinitionResponse | null
  exceptions: Map<AcademyDate, MockException>
  occurrenceDeletes: CalendarOccurrenceDeletePayload[]
  occurrenceUpdates: CalendarOccurrenceUpdatePayload[]
  seriesDeletes: number
}

function asDate(value: AcademyDate) {
  return new Date(`${value}T00:00:00Z`)
}

function isoDate(value: Date): AcademyDate {
  return value.toISOString().slice(0, 10)
}

function addDays(value: AcademyDate, days: number): AcademyDate {
  const next = asDate(value)
  next.setUTCDate(next.getUTCDate() + days)
  return isoDate(next)
}

function yearlyDate(firstDate: AcademyDate, year: number): AcademyDate {
  const [firstYear, month, day] = firstDate.split('-').map(Number)
  if (year < firstYear) return firstDate
  const candidate = new Date(Date.UTC(year, month - 1, day))
  if (month === 2 && day === 29 && candidate.getUTCMonth() !== 1) {
    return `${year}-02-28`
  }
  return isoDate(candidate)
}

function occurrenceDates(
  definition: CalendarEventDefinitionResponse,
  startDate: AcademyDate,
  endDate: AcademyDate,
): AcademyDate[] {
  if (definition.recurrence === null) {
    return definition.event_date >= startDate && definition.event_date <= endDate
      ? [definition.event_date]
      : []
  }
  const rule = definition.recurrence
  const dates: AcademyDate[] = []
  let index = 0
  while (index < 1000) {
    const candidate =
      rule.frequency === 'weekly'
        ? addDays(definition.event_date, index * 7)
        : yearlyDate(definition.event_date, asDate(definition.event_date).getUTCFullYear() + index)
    if (candidate > endDate) break
    if (rule.termination === 'end_date' && candidate > (rule.end_date ?? candidate)) break
    if (
      rule.termination === 'occurrence_count' &&
      index >= (rule.occurrence_count ?? 0)
    ) break
    if (candidate >= startDate) dates.push(candidate)
    index += 1
  }
  return dates
}

function recurrenceSummary(definition: CalendarEventDefinitionResponse) {
  if (definition.recurrence?.frequency === 'yearly') return 'Every year'
  return 'Every week on Wednesday'
}

function instanceFor(
  state: CalendarApiState,
  originalDate: AcademyDate,
): CalendarEventInstance | null {
  const definition = state.definition
  if (definition === null) return null
  const exception = state.exceptions.get(originalDate)
  if (exception?.deleted) return null
  const values = exception?.values ?? definition
  const recurrence = definition.recurrence
  return {
    occurrence_id:
      recurrence === null ? definition.id : `${recurrence.id}:${originalDate}`,
    event_id: definition.id,
    series_id: recurrence?.id ?? null,
    original_date: originalDate,
    event_date: exception?.values.event_date ?? originalDate,
    event_type: values.event_type,
    name: values.name,
    is_all_day: values.is_all_day,
    start_time: values.start_time,
    end_time: values.end_time,
    scope_kind: values.scope.scope_kind,
    age_groups: [...values.scope.age_groups],
    is_recurring: recurrence !== null,
    recurrence_summary:
      recurrence === null ? null : recurrenceSummary(definition),
    series_definition: recurrence === null ? null : definition,
    event_version_number: definition.version_number,
    exception_id: exception === undefined ? null : `exception-${originalDate}`,
    exception_version_number: exception?.version ?? null,
  }
}

function projectedEvents(
  state: CalendarApiState,
  startDate: AcademyDate,
  endDate: AcademyDate,
) {
  if (state.definition === null) return []
  return occurrenceDates(state.definition, startDate, endDate)
    .map((originalDate) => instanceFor(state, originalDate))
    .filter((event): event is CalendarEventInstance => event !== null)
    .filter((event) => event.event_date >= startDate && event.event_date <= endDate)
    .sort(
      (left, right) =>
        left.event_date.localeCompare(right.event_date) ||
        left.occurrence_id.localeCompare(right.occurrence_id),
    )
}

function definitionFromPayload(
  payload: CalendarEventCreatePayload,
): CalendarEventDefinitionResponse {
  return {
    ...payload,
    id: eventId,
    version_number: 1,
    recurrence:
      payload.recurrence === null
        ? null
        : {
            ...payload.recurrence,
            id: seriesId,
            event_id: eventId,
            weekday: payload.recurrence.frequency === 'weekly' ? 2 : null,
            month: payload.recurrence.frequency === 'yearly' ? 8 : null,
            month_day: payload.recurrence.frequency === 'yearly' ? 5 : null,
            created_at: timestamp,
            updated_at: timestamp,
          },
    created_at: timestamp,
    updated_at: timestamp,
  }
}

function originalDateFromPath(pathname: string) {
  const encoded = pathname.replace('/api/v1/calendar/instances/', '')
  return decodeURIComponent(encoded).split(':').at(-1) as AcademyDate
}

export async function installCalendarApiMock(
  page: Page,
): Promise<CalendarApiState> {
  const state: CalendarApiState = {
    createPayloads: [],
    definition: null,
    exceptions: new Map(),
    occurrenceDeletes: [],
    occurrenceUpdates: [],
    seriesDeletes: 0,
  }

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const { pathname, searchParams } = url

    if (pathname === '/api/v1/calendar/today' && request.method() === 'GET') {
      await route.fulfill({
        status: 200,
        json: {
          academy_today: academyToday,
          events: projectedEvents(state, academyToday, academyToday),
        },
      })
      return
    }

    if (pathname === '/api/v1/calendar/events' && request.method() === 'GET') {
      const startDate = searchParams.get('start_date') as AcademyDate
      const endDate = searchParams.get('end_date') as AcademyDate
      await route.fulfill({
        status: 200,
        json: {
          academy_today: academyToday,
          start_date: startDate,
          end_date: endDate,
          events: projectedEvents(state, startDate, endDate),
        },
      })
      return
    }

    if (pathname === '/api/v1/calendar/events' && request.method() === 'POST') {
      const payload = request.postDataJSON() as CalendarEventCreatePayload
      state.createPayloads.push(payload)
      state.definition = definitionFromPayload(payload)
      state.exceptions.clear()
      await route.fulfill({ status: 201, json: state.definition })
      return
    }

    if (
      pathname.startsWith('/api/v1/calendar/instances/') &&
      request.method() === 'GET'
    ) {
      const originalDate = originalDateFromPath(pathname)
      const instance = instanceFor(state, originalDate)
      await route.fulfill(
        instance === null
          ? { status: 404, json: { detail: 'This calendar event is no longer available.' } }
          : { status: 200, json: instance },
      )
      return
    }

    if (
      pathname.startsWith('/api/v1/calendar/instances/') &&
      request.method() === 'PATCH'
    ) {
      const payload = request.postDataJSON() as CalendarOccurrenceUpdatePayload
      const originalDate = originalDateFromPath(pathname)
      const current = state.exceptions.get(originalDate)
      state.occurrenceUpdates.push(payload)
      state.exceptions.set(originalDate, {
        values: {
          event_type: payload.event_type,
          name: payload.name,
          event_date: payload.event_date,
          is_all_day: payload.is_all_day,
          start_time: payload.start_time,
          end_time: payload.end_time,
          scope: payload.scope,
        },
        version: (current?.version ?? 0) + 1,
        deleted: false,
      })
      await route.fulfill({ status: 200, json: instanceFor(state, originalDate) })
      return
    }

    if (
      pathname.startsWith('/api/v1/calendar/instances/') &&
      request.method() === 'DELETE'
    ) {
      const payload = request.postDataJSON() as CalendarOccurrenceDeletePayload
      const originalDate = originalDateFromPath(pathname)
      const existing = state.exceptions.get(originalDate)
      state.occurrenceDeletes.push(payload)
      state.exceptions.set(originalDate, {
        values:
          existing?.values ?? {
            event_type: state.definition!.event_type,
            name: state.definition!.name,
            event_date: originalDate,
            is_all_day: state.definition!.is_all_day,
            start_time: state.definition!.start_time,
            end_time: state.definition!.end_time,
            scope: state.definition!.scope,
          },
        version: (existing?.version ?? 0) + 1,
        deleted: true,
      })
      await route.fulfill({ status: 204 })
      return
    }

    if (
      pathname === `/api/v1/calendar/series/${seriesId}` &&
      request.method() === 'PATCH'
    ) {
      const payload = request.postDataJSON() as CalendarSeriesUpdatePayload
      const removedDates = [...state.exceptions.keys()].filter(
        (originalDate) => originalDate < payload.event_date,
      )
      if (removedDates.length > 0 && !payload.confirm_exception_removals) {
        await route.fulfill({
          status: 422,
          json: {
            detail: `This change will remove saved changes for ${removedDates.length} occurrences.`,
            code: 'exception_removal_confirmation_required',
            removed_exception_original_dates: removedDates,
          },
        })
        return
      }
      removedDates.forEach((date) => state.exceptions.delete(date))
      state.definition = {
        ...state.definition!,
        ...payload,
        version_number: state.definition!.version_number + 1,
        recurrence: {
          ...state.definition!.recurrence!,
          ...payload.recurrence,
          updated_at: '2026-08-01T12:05:00Z',
        },
        updated_at: '2026-08-01T12:05:00Z',
      }
      await route.fulfill({ status: 200, json: state.definition })
      return
    }

    if (
      pathname === `/api/v1/calendar/series/${seriesId}` &&
      request.method() === 'DELETE'
    ) {
      state.seriesDeletes += 1
      state.definition = null
      state.exceptions.clear()
      await route.fulfill({ status: 204 })
      return
    }

    await route.fallback()
  })

  return state
}
