import { describe, expect, it, vi } from 'vitest'
import { apiClient, ApiClientError } from '@shared/api/client'
import {
  fetchCalendarInstance,
  fetchCalendarRange,
  fetchCalendarToday,
} from '@features/calendar/api/calendarApi'
import {
  getCalendarErrorMessage,
  getExceptionRemovalWarning,
} from '@features/calendar/utils/calendarErrors'

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
