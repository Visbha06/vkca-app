// @vitest-environment jsdom

import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '@features/auth'
import {
  fetchBusinessAuditActors,
  fetchBusinessAuditEvents,
  fetchRecentBusinessAudit,
} from '../api/businessAuditApi'
import { useBusinessAudit, useBusinessAuditActorOptions, useRecentBusinessAudit } from './useBusinessAudit'

vi.mock('../api/businessAuditApi', () => ({
  fetchBusinessAuditActors: vi.fn(), fetchBusinessAuditEvents: vi.fn(), fetchRecentBusinessAudit: vi.fn(),
}))

const auth: AuthContextValue = {
  user: { id: 'head', first_name: 'Asha', last_name: 'Coach', email: 'a@test', role: 'head coach', is_active: true, created_at: '', updated_at: '', session: { session_id: '', created_at: '', last_used_at: '', expires_at: '' } },
  isAuthenticated: true, isInitializing: false, isLoginPending: false, isLogoutPending: false,
  login: vi.fn(), logout: vi.fn(), refreshSession: vi.fn(), updateUser: vi.fn(),
}
const wrapper = ({ children }: { children: React.ReactNode }) => <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>
const emptyPage = { events: [], page: 1, page_size: 20, total_events: 0, total_pages: 0, has_previous: false, has_next: false }

describe('business audit query hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads, resets pagination when filters change, and retries', async () => {
    vi.mocked(fetchBusinessAuditEvents).mockResolvedValue(emptyPage)
    const { result } = renderHook(() => useBusinessAudit(), { wrapper })
    await waitFor(() => expect(result.current.result).toEqual(emptyPage))

    act(() => result.current.updateFilters({ actionCategory: 'player' }))
    await waitFor(() => expect(fetchBusinessAuditEvents).toHaveBeenLastCalledWith(
      { actionCategory: 'player', page: 1, pageSize: 20 }, expect.any(AbortSignal),
    ))
    act(() => result.current.retry())
    await waitFor(() => expect(fetchBusinessAuditEvents).toHaveBeenCalledTimes(3))
  })

  it('loads actor options and bounded recent activity for a Head Coach only', async () => {
    vi.mocked(fetchBusinessAuditActors).mockResolvedValue({ actors: [] })
    vi.mocked(fetchRecentBusinessAudit).mockResolvedValue({ events: [] })
    const actors = renderHook(() => useBusinessAuditActorOptions(), { wrapper })
    const recent = renderHook(() => useRecentBusinessAudit(), { wrapper })
    await waitFor(() => expect(actors.result.current.isLoading).toBe(false))
    await waitFor(() => expect(recent.result.current.isLoading).toBe(false))
    expect(fetchRecentBusinessAudit).toHaveBeenCalledWith(4, expect.any(AbortSignal))
  })

  it('keeps unauthorised roles from requesting audit data', async () => {
    const playerWrapper = ({ children }: { children: React.ReactNode }) => <AuthContext.Provider value={{ ...auth, user: { ...auth.user!, role: 'player' } }}>{children}</AuthContext.Provider>
    renderHook(() => useBusinessAuditActorOptions(), { wrapper: playerWrapper })
    renderHook(() => useRecentBusinessAudit(), { wrapper: playerWrapper })
    await act(async () => undefined)
    expect(fetchBusinessAuditActors).not.toHaveBeenCalled()
    expect(fetchRecentBusinessAudit).not.toHaveBeenCalled()
  })
})
