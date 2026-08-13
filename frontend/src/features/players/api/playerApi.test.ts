import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '@shared/api/client'
import {
  createPlayer,
  fetchEligiblePlayerAccounts,
  fetchPlayerAccountAssociation,
  fetchPlayer,
  fetchPlayers,
  fetchTeamsForFilter,
  linkPlayerAccount,
  reassignPlayerAccount,
  unlinkPlayerAccount,
  updatePlayer,
} from '@features/players/api/playerApi'
import type {
  PlayerCreatePayload,
  PlayerUpdatePayload,
} from '@features/players/types/player'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('player API client', () => {
  it('fetches the default player collection', async () => {
    const response = { players: [] }
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue(response)

    await expect(fetchPlayers()).resolves.toBe(response)

    expect(request).toHaveBeenCalledWith('/api/v1/players')
  })

  it('serializes pagination, trimmed search, and mutually exclusive filters', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ players: [] })
    const signal = new AbortController().signal

    await fetchPlayers(
      {
        page: 3,
        pageSize: 10,
        search: '  Asha Singh  ',
        teamId: 'team/one',
      },
      signal,
    )

    expect(request).toHaveBeenCalledWith(
      '/api/v1/players?page=3&page_size=10&search=Asha+Singh&team_id=team%2Fone',
      { signal },
    )

    await expect(
      fetchPlayers({ teamId: 'team-one', unassigned: true }),
    ).rejects.toThrow('teamId and unassigned are mutually exclusive')
  })

  it.each([undefined, '', '   '])(
    'omits an absent or blank search value (%s)',
    async (search) => {
      const request = vi
        .spyOn(apiClient, 'request')
        .mockResolvedValue({ players: [] })

      await fetchPlayers({ search })

      expect(request).toHaveBeenCalledWith('/api/v1/players')
    },
  )

  it('fetches an individual player', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ id: 'player/1' })

    await fetchPlayer('player/1')

    expect(request).toHaveBeenCalledWith('/api/v1/players/player%2F1')
  })

  it('fetches typed team options for the player filter', async () => {
    const response = {
      teams: [{ id: 'team-1', name: 'Junior XI', age_group: 'U13', player_count: 8 }],
    }
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue(response)
    const signal = new AbortController().signal

    await expect(fetchTeamsForFilter(signal)).resolves.toEqual([
      { id: 'team-1', name: 'Junior XI' },
    ])
    expect(request).toHaveBeenCalledWith('/api/v1/teams?page_size=100', { signal })
  })

  it('creates a player with the typed payload', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ id: 'player-1' })
    const payload: PlayerCreatePayload = {
      first_name: 'Anika',
      last_name: 'Patel',
      date_of_birth: '2001-02-03',
      batting_style: 'right',
      bowling_style: 'right-arm medium',
      player_type: 'batter',
    }

    await createPlayer(payload)

    expect(request).toHaveBeenCalledWith('/api/v1/players', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  })

  it('updates a player with its OCC version', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ id: 'player-1' })
    const payload: PlayerUpdatePayload = {
      bio: 'Updated bio',
      version_number: 3,
    }

    await updatePlayer('player-1', payload)

    expect(request).toHaveBeenCalledWith('/api/v1/players/player-1', {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  })

  it('fetches a bounded safe account lookup and the protected association', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ users: [] })
    const signal = new AbortController().signal

    await fetchEligiblePlayerAccounts(
      { search: '  Rohan Patel  ', page: 2, pageSize: 25 },
      signal,
    )
    await fetchPlayerAccountAssociation('player/1', signal)

    expect(request).toHaveBeenNthCalledWith(
      1,
      '/api/v1/players/account-linking/users?search=Rohan+Patel&page=2&page_size=25',
      { signal },
    )
    expect(request).toHaveBeenNthCalledWith(
      2,
      '/api/v1/players/player%2F1/account',
      { signal },
    )
  })

  it('sends typed OCC link, unlink, and reassignment mutations', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({
      player_id: 'player-1',
      account: null,
      player_version_number: 2,
    })

    await linkPlayerAccount('player-1', {
      user_id: 'account-1',
      version_number: 1,
    })
    await unlinkPlayerAccount('player-1', { version_number: 2 })
    await reassignPlayerAccount('player-1', {
      expected_user_id: 'account-1',
      new_user_id: 'account-2',
      version_number: 3,
    })

    expect(request).toHaveBeenNthCalledWith(1, '/api/v1/players/player-1/account', {
      method: 'PUT',
      body: JSON.stringify({ user_id: 'account-1', version_number: 1 }),
    })
    expect(request).toHaveBeenNthCalledWith(2, '/api/v1/players/player-1/account', {
      method: 'DELETE',
      body: JSON.stringify({ version_number: 2 }),
    })
    expect(request).toHaveBeenNthCalledWith(
      3,
      '/api/v1/players/player-1/account/reassign',
      {
        method: 'POST',
        body: JSON.stringify({
          expected_user_id: 'account-1',
          new_user_id: 'account-2',
          version_number: 3,
        }),
      },
    )
  })
})
