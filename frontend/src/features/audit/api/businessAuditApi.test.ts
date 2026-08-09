import { beforeEach, describe, expect, it, vi } from 'vitest'

const { request } = vi.hoisted(() => ({ request: vi.fn() }))

vi.mock('@shared/api/client', () => ({ apiClient: { request } }))

import {
  fetchBusinessAuditActors,
  fetchBusinessAuditEvents,
  fetchRecentBusinessAudit,
} from './businessAuditApi'

describe('businessAuditApi', () => {
  beforeEach(() => request.mockReset())

  it('serializes full-log filters and pagination', () => {
    const signal = new AbortController().signal
    void fetchBusinessAuditEvents({
      page: 2, pageSize: 50, actorUserId: 'actor-1', actionCategory: 'player',
      actionType: 'player.created', entityType: 'player', startDate: '2026-08-01', endDate: '2026-08-02',
    }, signal)

    expect(request).toHaveBeenCalledWith(
      '/api/v1/audit-log?page=2&page_size=50&actor_user_id=actor-1&action_category=player&action_type=player.created&entity_type=player&start_date=2026-08-01&end_date=2026-08-02',
      { signal },
    )
  })

  it('maps pagination and recent bounds to safe local errors', async () => {
    await expect(fetchBusinessAuditEvents({ page: 0 })).rejects.toThrow('page must')
    await expect(fetchBusinessAuditEvents({ pageSize: 101 })).rejects.toThrow('pageSize')
    await expect(fetchRecentBusinessAudit(5)).rejects.toThrow('between 1 and 4')
    expect(request).not.toHaveBeenCalled()
  })

  it('forwards abort signals for actors and bounded recent activity', () => {
    const signal = new AbortController().signal
    void fetchBusinessAuditActors(signal)
    void fetchRecentBusinessAudit(4, signal)

    expect(request).toHaveBeenNthCalledWith(1, '/api/v1/audit-log/actors', { signal })
    expect(request).toHaveBeenNthCalledWith(2, '/api/v1/audit-log/recent?limit=4', { signal })
  })
})
