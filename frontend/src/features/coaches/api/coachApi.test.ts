import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '@shared/api/client'
import {
  createCoach,
  deactivateCoach,
  fetchCoachDetails,
  fetchCoaches,
  reactivateCoach,
  updateTeamAssignments,
} from './coachApi'
import type { CoachCreatePayload } from '../types/coach'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('coach API client', () => {
  it('fetches filtered pages and encoded coach details', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({})
    const signal = new AbortController().signal

    await fetchCoaches(
      { status: 'inactive', page: 2, pageSize: 12 },
      signal,
    )
    await fetchCoachDetails('coach/one', signal)

    expect(request).toHaveBeenNthCalledWith(
      1,
      '/api/v1/coaches?status=inactive&page=2&page_size=12',
      { signal },
    )
    expect(request).toHaveBeenNthCalledWith(
      2,
      '/api/v1/coaches/coach%2Fone',
      { signal },
    )
  })

  it('creates a coach with the typed payload', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({})
    const payload: CoachCreatePayload = {
      first_name: 'Asha',
      last_name: 'Patel',
      email: 'asha@vkca.test',
      team_ids: ['team-1'],
    }

    await createCoach(payload)

    expect(request).toHaveBeenCalledWith('/api/v1/coaches', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  })

  it('sends OCC versions for deactivation and reactivation', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({})

    await deactivateCoach('coach/one', 3)
    await reactivateCoach('coach/one', 4)

    expect(request).toHaveBeenNthCalledWith(
      1,
      '/api/v1/users/coach%2Fone/disable',
      {
        method: 'POST',
        body: JSON.stringify({ version_number: 3 }),
      },
    )
    expect(request).toHaveBeenNthCalledWith(
      2,
      '/api/v1/users/coach%2Fone/reactivate',
      {
        method: 'POST',
        body: JSON.stringify({ version_number: 4 }),
      },
    )
  })

  it('replaces team assignments with the complete typed set and OCC version', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({})
    const payload = {
      team_ids: ['team-1', 'team-2'],
      version_number: 5,
    }

    await updateTeamAssignments('coach/one', payload)

    expect(request).toHaveBeenCalledWith(
      '/api/v1/coaches/coach%2Fone/teams',
      {
        method: 'PUT',
        body: JSON.stringify(payload),
      },
    )
  })
})
