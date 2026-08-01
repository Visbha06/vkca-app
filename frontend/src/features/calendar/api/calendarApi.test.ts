// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiClient, ApiClientError } from '@shared/api/client'
import {
  createCalendarEvent,
  deleteCalendarOccurrence,
  deleteCalendarSeries,
  deleteStandaloneCalendarEvent,
  fetchCalendarInstance,
  fetchCalendarRange,
  fetchCalendarToday,
  updateCalendarOccurrence,
  updateCalendarSeries,
  updateStandaloneCalendarEvent,
} from '@features/calendar/api/calendarApi'
import {
  getCalendarErrorMessage,
  getExceptionRemovalWarning,
} from '@features/calendar/utils/calendarErrors'

const eventValues = {
  event_type: 'practice' as const,
  name: 'Wednesday practice',
  event_date: '2026-08-05',
  is_all_day: false,
  start_time: '17:00:00',
  end_time: '18:30:00',
  scope: { scope_kind: 'age_group' as const, age_groups: ['U13' as const] },
}

afterEach(() => {
  vi.restoreAllMocks()
  document.cookie = 'csrf_token=; Max-Age=0; path=/'
})

describe('calendarApi read operations', () => {
  it('serializes an inclusive range and forwards AbortSignal', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({
      academy_today: '2026-08-01',
      start_date: '2026-07-26',
      end_date: '2026-09-05',
      events: [],
    })
    const signal = new AbortController().signal

    await fetchCalendarRange(
      { startDate: '2026-07-26', endDate: '2026-09-05' },
      signal,
    )

    expect(request).toHaveBeenCalledWith(
      '/api/v1/calendar/events?start_date=2026-07-26&end_date=2026-09-05',
      { signal },
    )
  })

  it('loads Today independently and encodes stable occurrence identities', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ events: [] })
    const signal = new AbortController().signal

    await fetchCalendarToday(signal)
    await fetchCalendarInstance('series/1:2026-08-05', signal)

    expect(request).toHaveBeenNthCalledWith(1, '/api/v1/calendar/today', { signal })
    expect(request).toHaveBeenNthCalledWith(
      2,
      '/api/v1/calendar/instances/series%2F1%3A2026-08-05',
      { signal },
    )
  })

  it('maps safe status and warning responses without exposing raw errors', () => {
    const forbidden = new ApiClientError(403, {
      detail: 'internal authorization details',
    })
    const conflict = new ApiClientError(409, { detail: 'database exception' })
    const warning = new ApiClientError(422, {
      detail: 'internal validation detail',
      code: 'exception_removal_confirmation_required',
      removed_exception_original_dates: ['2026-08-05', '2026-08-12'],
    })

    expect(getCalendarErrorMessage(forbidden)).toBe(
      'You do not have permission to make this calendar change.',
    )
    expect(getCalendarErrorMessage(conflict)).toBe(
      'This event changed since you opened it. Reload before trying again.',
    )
    expect(getExceptionRemovalWarning(warning)).toEqual({
      code: 'exception_removal_confirmation_required',
      detail: 'This change will remove saved changes for 2 occurrences.',
      removed_exception_original_dates: ['2026-08-05', '2026-08-12'],
    })
  })
})

describe('calendarApi mutation operations', () => {
  it('sends complete create, standalone, occurrence, and series payloads', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue(undefined)
    const signal = new AbortController().signal
    const recurrence = {
      frequency: 'weekly' as const,
      termination: 'occurrence_count' as const,
      end_date: null,
      occurrence_count: 4,
    }

    await createCalendarEvent({ ...eventValues, recurrence }, signal)
    await updateStandaloneCalendarEvent(
      'event/1',
      { ...eventValues, version_number: 2 },
      signal,
    )
    await updateCalendarOccurrence(
      'series/1:2026-08-05',
      {
        ...eventValues,
        event_date: '2026-08-06',
        version_number: 3,
        exception_version_number: 1,
      },
      signal,
    )
    await updateCalendarSeries(
      'series/1',
      {
        ...eventValues,
        recurrence,
        version_number: 3,
        confirm_exception_removals: true,
      },
      signal,
    )

    expect(request).toHaveBeenNthCalledWith(1, '/api/v1/calendar/events', {
      method: 'POST',
      body: JSON.stringify({ ...eventValues, recurrence }),
      signal,
    })
    expect(request).toHaveBeenNthCalledWith(
      2,
      '/api/v1/calendar/events/event%2F1',
      {
        method: 'PATCH',
        body: JSON.stringify({ ...eventValues, version_number: 2 }),
        signal,
      },
    )
    expect(request).toHaveBeenNthCalledWith(
      3,
      '/api/v1/calendar/instances/series%2F1%3A2026-08-05',
      {
        method: 'PATCH',
        body: JSON.stringify({
          ...eventValues,
          event_date: '2026-08-06',
          version_number: 3,
          exception_version_number: 1,
        }),
        signal,
      },
    )
    expect(request).toHaveBeenNthCalledWith(
      4,
      '/api/v1/calendar/series/series%2F1',
      {
        method: 'PATCH',
        body: JSON.stringify({
          ...eventValues,
          recurrence,
          version_number: 3,
          confirm_exception_removals: true,
        }),
        signal,
      },
    )
  })

  it('sends owning-event and exception versions with every delete shape', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue(undefined)

    await deleteStandaloneCalendarEvent('event-1', { version_number: 2 })
    await deleteCalendarOccurrence('series-1:2026-08-05', {
      version_number: 3,
      exception_version_number: 1,
    })
    await deleteCalendarSeries('series-1', { version_number: 4 })

    expect(request).toHaveBeenNthCalledWith(
      1,
      '/api/v1/calendar/events/event-1',
      { method: 'DELETE', body: JSON.stringify({ version_number: 2 }) },
    )
    expect(request).toHaveBeenNthCalledWith(
      2,
      '/api/v1/calendar/instances/series-1%3A2026-08-05',
      {
        method: 'DELETE',
        body: JSON.stringify({
          version_number: 3,
          exception_version_number: 1,
        }),
      },
    )
    expect(request).toHaveBeenNthCalledWith(
      3,
      '/api/v1/calendar/series/series-1',
      { method: 'DELETE', body: JSON.stringify({ version_number: 4 }) },
    )
  })

  it('remains CSRF-compatible and never retries a conflict automatically', async () => {
    document.cookie = 'csrf_token=calendar-csrf; path=/'
    apiClient.setAccessToken('calendar-token')
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: 'Stale calendar event.',
          code: 'calendar_stale_version',
        }),
        {
          status: 409,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    )

    await expect(
      createCalendarEvent({ ...eventValues, recurrence: null }),
    ).rejects.toMatchObject({ status: 409 })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const options = fetchMock.mock.calls[0][1]
    expect(new Headers(options?.headers).get('X-CSRF-Token')).toBe(
      'calendar-csrf',
    )
  })
})
