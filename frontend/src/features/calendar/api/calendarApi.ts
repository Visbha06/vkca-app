import { apiClient } from '@shared/api/client'
import type {
  AcademyDate,
  CalendarEventCreatePayload,
  CalendarEventDefinitionResponse,
  CalendarEventDeletePayload,
  CalendarEventInstance,
  CalendarOccurrenceDeletePayload,
  CalendarOccurrenceUpdatePayload,
  CalendarRangeResponse,
  CalendarSeriesUpdatePayload,
  CalendarStandaloneUpdatePayload,
  CalendarTodayResponse,
} from '../types/calendar'

const CALENDAR_PATH = '/api/v1/calendar'
const EVENTS_PATH = `${CALENDAR_PATH}/events`
const TODAY_PATH = `${CALENDAR_PATH}/today`

export interface CalendarRangeParams {
  startDate: AcademyDate
  endDate: AcademyDate
}

function eventPath(eventId: string) {
  return `${EVENTS_PATH}/${encodeURIComponent(eventId)}`
}

function instancePath(occurrenceId: string) {
  return `${CALENDAR_PATH}/instances/${encodeURIComponent(occurrenceId)}`
}

function seriesPath(seriesId: string) {
  return `${CALENDAR_PATH}/series/${encodeURIComponent(seriesId)}`
}

function requestSignal(signal: AbortSignal | undefined): RequestInit | undefined {
  return signal === undefined ? undefined : { signal }
}

export function fetchCalendarRange(
  params: CalendarRangeParams,
  signal?: AbortSignal,
) {
  const query = new URLSearchParams({
    start_date: params.startDate,
    end_date: params.endDate,
  })
  return apiClient.request<CalendarRangeResponse>(
    `${EVENTS_PATH}?${query.toString()}`,
    requestSignal(signal),
  )
}

export function fetchCalendarToday(signal?: AbortSignal) {
  return apiClient.request<CalendarTodayResponse>(
    TODAY_PATH,
    requestSignal(signal),
  )
}

export function fetchCalendarInstance(
  occurrenceId: string,
  signal?: AbortSignal,
) {
  return apiClient.request<CalendarEventInstance>(
    instancePath(occurrenceId),
    requestSignal(signal),
  )
}

export function createCalendarEvent(
  payload: CalendarEventCreatePayload,
  signal?: AbortSignal,
) {
  return apiClient.request<CalendarEventDefinitionResponse>(EVENTS_PATH, {
    method: 'POST',
    body: JSON.stringify(payload),
    ...(signal === undefined ? {} : { signal }),
  })
}

export function updateStandaloneCalendarEvent(
  eventId: string,
  payload: CalendarStandaloneUpdatePayload,
  signal?: AbortSignal,
) {
  return apiClient.request<CalendarEventDefinitionResponse>(
    eventPath(eventId),
    {
      method: 'PATCH',
      body: JSON.stringify(payload),
      ...(signal === undefined ? {} : { signal }),
    },
  )
}

export function deleteStandaloneCalendarEvent(
  eventId: string,
  payload: CalendarEventDeletePayload,
  signal?: AbortSignal,
) {
  return apiClient.request<void>(eventPath(eventId), {
    method: 'DELETE',
    body: JSON.stringify(payload),
    ...(signal === undefined ? {} : { signal }),
  })
}

export function updateCalendarOccurrence(
  occurrenceId: string,
  payload: CalendarOccurrenceUpdatePayload,
  signal?: AbortSignal,
) {
  return apiClient.request<CalendarEventInstance>(
    instancePath(occurrenceId),
    {
      method: 'PATCH',
      body: JSON.stringify(payload),
      ...(signal === undefined ? {} : { signal }),
    },
  )
}

export function deleteCalendarOccurrence(
  occurrenceId: string,
  payload: CalendarOccurrenceDeletePayload,
  signal?: AbortSignal,
) {
  return apiClient.request<void>(instancePath(occurrenceId), {
    method: 'DELETE',
    body: JSON.stringify(payload),
    ...(signal === undefined ? {} : { signal }),
  })
}

export function updateCalendarSeries(
  seriesId: string,
  payload: CalendarSeriesUpdatePayload,
  signal?: AbortSignal,
) {
  return apiClient.request<CalendarEventDefinitionResponse>(
    seriesPath(seriesId),
    {
      method: 'PATCH',
      body: JSON.stringify(payload),
      ...(signal === undefined ? {} : { signal }),
    },
  )
}

export function deleteCalendarSeries(
  seriesId: string,
  payload: CalendarEventDeletePayload,
  signal?: AbortSignal,
) {
  return apiClient.request<void>(seriesPath(seriesId), {
    method: 'DELETE',
    body: JSON.stringify(payload),
    ...(signal === undefined ? {} : { signal }),
  })
}
