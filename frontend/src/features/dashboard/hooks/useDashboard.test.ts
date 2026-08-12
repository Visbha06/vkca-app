// @vitest-environment jsdom

import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchDashboard } from '../api/dashboardApi'
import { dashboardFixture } from '../test/dashboardFixture'
import { useDashboard } from './useDashboard'

vi.mock('../api/dashboardApi', () => ({ fetchDashboard: vi.fn() }))

describe('useDashboard', () => {
  beforeEach(() => vi.clearAllMocks())

  it('moves from an initial loading state to populated live data', async () => {
    const dashboard = dashboardFixture()
    vi.mocked(fetchDashboard).mockResolvedValue(dashboard)

    const { result } = renderHook(() => useDashboard())

    expect(result.current.isInitialLoading).toBe(true)
    expect(result.current.result).toBeNull()
    await waitFor(() => expect(result.current.result).toEqual(dashboard))
    expect(result.current.isFetching).toBe(false)
    expect(result.current.errorMessage).toBeNull()
  })

  it('shows an initial failure without static fallback values and retries', async () => {
    vi.mocked(fetchDashboard)
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(dashboardFixture())
    const { result } = renderHook(() => useDashboard())

    await waitFor(() => expect(result.current.errorMessage).not.toBeNull())
    expect(result.current.result).toBeNull()
    expect(JSON.stringify(result.current)).not.toContain('84')

    act(() => result.current.retry())
    await waitFor(() => expect(result.current.result).toEqual(dashboardFixture()))
    expect(fetchDashboard).toHaveBeenCalledTimes(2)
  })

  it('retains populated content during a background refresh failure', async () => {
    const dashboard = dashboardFixture()
    vi.mocked(fetchDashboard)
      .mockResolvedValueOnce(dashboard)
      .mockRejectedValueOnce(new Error('temporary'))
    const { result } = renderHook(() => useDashboard())
    await waitFor(() => expect(result.current.result).toEqual(dashboard))

    act(() => result.current.retry())
    expect(result.current.result).toEqual(dashboard)
    expect(result.current.isFetching).toBe(true)
    await waitFor(() => expect(result.current.errorMessage).not.toBeNull())
    expect(result.current.result).toEqual(dashboard)
  })

  it('forwards an AbortSignal and retries failed sections through one live read', async () => {
    vi.mocked(fetchDashboard).mockResolvedValue(dashboardFixture())
    const { result } = renderHook(() => useDashboard())
    await waitFor(() => expect(result.current.result).not.toBeNull())

    act(() => result.current.retry())
    await waitFor(() => expect(fetchDashboard).toHaveBeenCalledTimes(2))
    expect(fetchDashboard).toHaveBeenLastCalledWith(expect.any(AbortSignal))
  })
})
