// @vitest-environment jsdom

import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchCalendarRange, fetchCalendarToday } from '../api/calendarApi'
import useCalendarData from './useCalendarData'

vi.mock('../api/calendarApi', () => ({
  fetchCalendarRange: vi.fn(),
  fetchCalendarToday: vi.fn(),
  fetchCalendarInstance: vi.fn(),
}))

const mockedFetchRange = vi.mocked(fetchCalendarRange)
const mockedFetchToday = vi.mocked(fetchCalendarToday)

function todayResponse() {
  return {
    academy_today: '2026-08-05',
    events: [],
  }
}

function rangeResponse(name: string) {
  return {
    academy_today: '2026-08-05',
    start_date: '2026-07-26',
    end_date: '2026-09-05',
    events: [
      {
        occurrence_id: name,
        event_id: name,
        series_id: null,
        original_date: '2026-08-05',
        event_date: '2026-08-05',
        event_type: 'practice' as const,
        name,
        is_all_day: false,
        start_time: '17:00:00',
        end_time: '18:00:00',
        scope_kind: 'age_group' as const,
        age_groups: ['U13' as const],
        is_recurring: false,
        recurrence_summary: null,
        event_version_number: 1,
        exception_id: null,
        exception_version_number: null,
      },
    ],
  }
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('useCalendarData', () => {
  it('loads Today first, bootstraps the academy month, and requests its complete grid', async () => {
    mockedFetchToday.mockResolvedValue(todayResponse())
    mockedFetchRange.mockResolvedValue(rangeResponse('August practice'))

    const { result } = renderHook(() => useCalendarData())

    await waitFor(() => expect(mockedFetchToday).toHaveBeenCalled())
    await waitFor(() => expect(mockedFetchRange).toHaveBeenCalled())
    await waitFor(() => expect(result.current.isRangeLoading).toBe(false))

    expect(mockedFetchToday).toHaveBeenCalled()
    expect(mockedFetchRange).toHaveBeenCalled()
    expect(mockedFetchRange).toHaveBeenCalledWith(
      { startDate: '2026-07-26', endDate: '2026-09-05' },
      expect.any(AbortSignal),
    )
    expect(result.current.viewMonth).toEqual({ year: 2026, month: 8 })
    expect(result.current.events[0].name).toBe('August practice')
  })

  it('reloads the newly visible grid and preserves the selected month across year changes', async () => {
    mockedFetchToday.mockResolvedValue(todayResponse())
    mockedFetchRange.mockResolvedValue(rangeResponse('Initial'))
    const { result } = renderHook(() => useCalendarData())
    await waitFor(() => expect(mockedFetchRange).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(result.current.isRangeLoading).toBe(false))

    mockedFetchRange.mockResolvedValue(rangeResponse('September'))
    act(() => result.current.goToNextMonth())
    await waitFor(() => expect(result.current.events[0]?.name).toBe('September'))

    expect(result.current.viewMonth).toEqual({ year: 2026, month: 9 })
    expect(mockedFetchRange).toHaveBeenLastCalledWith(
      { startDate: '2026-08-30', endDate: '2026-10-03' },
      expect.any(AbortSignal),
    )

    act(() => result.current.goToYear(2028))
    expect(result.current.viewMonth).toEqual({ year: 2028, month: 9 })
  })

  it('ignores a superseded range response', async () => {
    mockedFetchToday.mockResolvedValue(todayResponse())
    let resolveFirst: ((value: ReturnType<typeof rangeResponse>) => void) | undefined
    let resolveSecond: ((value: ReturnType<typeof rangeResponse>) => void) | undefined
    mockedFetchRange
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve }))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve }))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve }))

    const { result } = renderHook(() => useCalendarData())
    await waitFor(() => expect(mockedFetchRange).toHaveBeenCalledTimes(1))

    act(() => result.current.goToNextMonth())
    act(() => result.current.goToNextMonth())
    await waitFor(() => expect(mockedFetchRange).toHaveBeenCalledTimes(3))

    await act(async () => {
      resolveSecond?.(rangeResponse('Newest'))
    })
    await waitFor(() => expect(result.current.events[0]?.name).toBe('Newest'))

    await act(async () => {
      resolveFirst?.(rangeResponse('Stale'))
    })
    expect(result.current.events[0]?.name).toBe('Newest')
  })
})
