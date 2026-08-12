import { beforeEach, describe, expect, it, vi } from 'vitest'

const { request } = vi.hoisted(() => ({ request: vi.fn() }))

vi.mock('@shared/api/client', () => ({ apiClient: { request } }))

import { fetchDashboard } from './dashboardApi'

describe('dashboardApi', () => {
  beforeEach(() => request.mockReset())

  it('requests only the authenticated current-user dashboard', () => {
    const signal = new AbortController().signal

    void fetchDashboard(signal)

    expect(request).toHaveBeenCalledWith('/api/v1/dashboard', { signal })
  })

  it('does not expose a client-selected scope argument', () => {
    expect(fetchDashboard).toHaveLength(1)
  })
})
