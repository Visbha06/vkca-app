// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClientError } from '@shared/api/client'
import { fetchCoachDetails } from '../api/coachApi'
import useConflictHandler from './useConflictHandler'
import type { CoachResponse } from '../types/coach'

vi.mock('../api/coachApi', () => ({
  fetchCoachDetails: vi.fn(),
}))

const coach: CoachResponse = {
  id: 'coach-1',
  first_name: 'Asha',
  last_name: 'Patel',
  email: 'asha@vkca.test',
  role: 'assistant coach',
  is_active: true,
  version_number: 3,
  created_at: '',
  updated_at: '',
  teams: [{ id: 'team-1', name: 'U11 Falcons' }],
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('useConflictHandler', () => {
  it('detects 409 responses and preserves the stale coach until reload', () => {
    const { result } = renderHook(() => useConflictHandler({ coach }))

    act(() => {
      expect(result.current.handleConflict(new Error('network error'))).toBe(false)
    })
    expect(result.current.hasConflict).toBe(false)

    act(() => {
      expect(
        result.current.handleConflict(
          new ApiClientError(409, { detail: 'Stale version' }),
        ),
      ).toBe(true)
    })

    expect(result.current.hasConflict).toBe(true)
    expect(result.current.staleCoach).toEqual(coach)
    expect(result.current.conflictMessage).toMatch(/updated by another user/i)
  })

  it('reloads current coach data, clears stale state, and notifies its owner', async () => {
    const onCoachReloaded = vi.fn()
    const latestCoach = {
      ...coach,
      version_number: 4,
      teams: [{ id: 'team-2', name: 'U13 Lions' }],
    }
    vi.mocked(fetchCoachDetails).mockResolvedValue(latestCoach)
    const { result } = renderHook(() =>
      useConflictHandler({ coach, onCoachReloaded }),
    )

    act(() => {
      result.current.handleConflict(
        new ApiClientError(409, { detail: 'Stale version' }),
      )
    })

    await act(async () => {
      await expect(result.current.reloadCoach()).resolves.toEqual(latestCoach)
    })

    expect(fetchCoachDetails).toHaveBeenCalledWith(coach.id)
    expect(onCoachReloaded).toHaveBeenCalledWith(latestCoach)
    expect(result.current.hasConflict).toBe(false)
    expect(result.current.staleCoach).toBeNull()
  })
})
