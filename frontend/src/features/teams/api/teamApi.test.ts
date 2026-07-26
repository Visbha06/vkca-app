import { describe, expect, it, vi } from 'vitest'
import { apiClient } from '@shared/api/client'
import {
  createTeam,
  fetchTeamRoster,
  fetchTeams,
  updateTeam,
} from '@features/teams/api/teamApi'
import type {
  TeamCreatePayload,
  TeamUpdatePayload,
} from '@features/teams/types/team'

describe('teamApi', () => {
  it('requests a typed paginated team list and forwards an abort signal', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ teams: [] })
    const signal = new AbortController().signal

    await fetchTeams({ page: 2, pageSize: 12 }, signal)

    expect(request).toHaveBeenCalledWith('/api/v1/teams?page=2&page_size=12', { signal })
  })

  it('creates and updates typed team payloads', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ id: 'team-1' })
    const createPayload: TeamCreatePayload = { name: 'Falcons', age_group: 'U13', player_ids: ['p1'] }
    const updatePayload: TeamUpdatePayload = { ...createPayload, version_number: 2 }

    await createTeam(createPayload)
    await updateTeam('team/1', updatePayload)

    expect(request).toHaveBeenNthCalledWith(1, '/api/v1/teams', { method: 'POST', body: JSON.stringify(createPayload) })
    expect(request).toHaveBeenNthCalledWith(2, '/api/v1/teams/team%2F1', { method: 'PUT', body: JSON.stringify(updatePayload) })
  })

  it('fetches a roster with an encoded team id and signal', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ players: [] })
    const signal = new AbortController().signal

    await fetchTeamRoster('team/1', signal)

    expect(request).toHaveBeenCalledWith('/api/v1/teams/team%2F1/players', { signal })
  })
})
