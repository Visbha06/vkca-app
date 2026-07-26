import type { Page } from '@playwright/test'
import type {
  PaginatedPlayerResponse,
  PlayerCreatePayload,
  PlayerResponse,
  PlayerUpdatePayload,
  TeamSummary,
} from '@features/players/types/player'

const teams: TeamSummary[] = [
  { id: 'team-junior', name: 'Junior XI' },
  { id: 'team-senior', name: 'Senior XI' },
]

const initialPlayers: PlayerResponse[] = [
  {
    id: 'player-asha',
    first_name: 'Asha',
    last_name: 'Singh',
    date_of_birth: '2008-04-24',
    bio: 'Opening batter',
    batting_style: 'right',
    bowling_style: 'right-arm medium',
    player_type: 'all-rounder',
    player_metadata: { squad_number: 12 },
    is_active: true,
    created_at: '2026-07-01T10:00:00Z',
    updated_at: '2026-07-15T10:00:00Z',
    version_number: 1,
    teams: [teams[0]],
  },
  {
    id: 'player-maya',
    first_name: 'Maya',
    last_name: 'Patel',
    date_of_birth: '2009-06-12',
    bio: null,
    batting_style: 'left',
    bowling_style: 'left-arm orthodox',
    player_type: 'all-rounder',
    player_metadata: {},
    is_active: true,
    created_at: '2026-07-02T10:00:00Z',
    updated_at: '2026-07-16T10:00:00Z',
    version_number: 1,
    teams: [teams[1]],
  },
  {
    id: 'player-dev',
    first_name: 'Dev',
    last_name: 'Rao',
    date_of_birth: '2007-11-03',
    bio: null,
    batting_style: 'right',
    bowling_style: 'right-arm fast',
    player_type: 'bowler',
    player_metadata: {},
    is_active: true,
    created_at: '2026-07-03T10:00:00Z',
    updated_at: '2026-07-17T10:00:00Z',
    version_number: 1,
    teams: [],
  },
]

export interface PlayersApiState {
  creates: number
  filters: string[]
  players: PlayerResponse[]
  searches: string[]
  updates: number
}

function paginatedResponse(
  players: PlayerResponse[],
  page: number,
  pageSize: number,
): PaginatedPlayerResponse {
  const totalPlayers = players.length
  const totalPages = Math.ceil(totalPlayers / pageSize)
  return {
    players: players.slice((page - 1) * pageSize, page * pageSize),
    page,
    page_size: pageSize,
    total_players: totalPlayers,
    total_pages: totalPages,
    has_previous: page > 1,
    has_next: page < totalPages,
  }
}

export async function installPlayersApiMock(
  page: Page,
): Promise<PlayersApiState> {
  const state: PlayersApiState = {
    creates: 0,
    filters: [],
    players: structuredClone(initialPlayers),
    searches: [],
    updates: 0,
  }

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const { pathname, searchParams } = url

    if (pathname === '/api/v1/teams' && request.method() === 'GET') {
      await route.fulfill({
        status: 200,
        json: {
          teams: teams.map((team) => ({
            ...team,
            age_group: 'U13',
            player_count: state.players.filter((player) =>
              player.teams.some(({ id }) => id === team.id),
            ).length,
            created_at: '2026-07-01T10:00:00Z',
            updated_at: '2026-07-01T10:00:00Z',
            version_number: 1,
          })),
          page: 1,
          page_size: 100,
          total_teams: teams.length,
          total_pages: 1,
        },
      })
      return
    }

    if (pathname === '/api/v1/players' && request.method() === 'GET') {
      const teamId = searchParams.get('team_id')
      const unassigned = searchParams.get('unassigned') === 'true'
      const search = searchParams.get('search')?.trim().toLocaleLowerCase() ?? ''
      const pageNumber = Number(searchParams.get('page') ?? 1)
      const pageSize = Number(searchParams.get('page_size') ?? 20)
      state.filters.push(teamId ?? (unassigned ? 'unassigned' : 'all'))
      state.searches.push(search)
      const filteredPlayers = state.players
        .filter((player) => player.is_active)
        .filter((player) =>
          search === ''
            ? true
            : `${player.first_name} ${player.last_name}`
                .toLocaleLowerCase()
                .includes(search),
        )
        .filter((player) =>
          teamId
            ? player.teams.some((team) => team.id === teamId)
            : unassigned
              ? player.teams.length === 0
              : true,
        )
        .sort(
          (left, right) =>
            left.last_name.localeCompare(right.last_name) ||
            left.first_name.localeCompare(right.first_name) ||
            left.id.localeCompare(right.id),
        )
      await route.fulfill({
        status: 200,
        json: paginatedResponse(filteredPlayers, pageNumber, pageSize),
      })
      return
    }

    if (pathname === '/api/v1/players' && request.method() === 'POST') {
      const payload = request.postDataJSON() as PlayerCreatePayload
      state.creates += 1
      const createdPlayer: PlayerResponse = {
        ...payload,
        id: `player-created-${state.creates}`,
        bio: payload.bio ?? null,
        player_metadata: payload.player_metadata ?? {},
        is_active: true,
        created_at: '2026-07-22T20:00:00Z',
        updated_at: '2026-07-22T20:00:00Z',
        version_number: 1,
        teams: [],
      }
      state.players.push(createdPlayer)
      await route.fulfill({ status: 201, json: createdPlayer })
      return
    }

    const playerMatch = pathname.match(/^\/api\/v1\/players\/([^/]+)$/)
    if (playerMatch && request.method() === 'GET') {
      const player = state.players.find(({ id }) => id === playerMatch[1])
      await route.fulfill(
        player
          ? { status: 200, json: player }
          : { status: 404, json: { detail: 'Player not found.' } },
      )
      return
    }

    if (playerMatch && request.method() === 'PUT') {
      const playerIndex = state.players.findIndex(
        ({ id }) => id === playerMatch[1],
      )
      if (playerIndex === -1) {
        await route.fulfill({
          status: 404,
          json: { detail: 'Player not found.' },
        })
        return
      }
      const payload = request.postDataJSON() as PlayerUpdatePayload
      const currentPlayer = state.players[playerIndex]
      const updatedPlayer: PlayerResponse = {
        ...currentPlayer,
        ...payload,
        bio: payload.bio ?? currentPlayer.bio,
        player_metadata:
          payload.player_metadata ?? currentPlayer.player_metadata,
        version_number: currentPlayer.version_number + 1,
        updated_at: '2026-07-22T20:05:00Z',
      }
      state.players[playerIndex] = updatedPlayer
      state.updates += 1
      await route.fulfill({ status: 200, json: updatedPlayer })
      return
    }

    await route.fallback()
  })

  return state
}
