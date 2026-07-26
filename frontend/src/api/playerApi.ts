import { apiClient } from './client'
import type {
  PaginatedPlayerResponse,
  PlayerCreatePayload,
  PlayerResponse,
  PlayerUpdatePayload,
  TeamSummary,
} from '../types/player'
import type { PaginatedTeamResponse } from '../types/team'

const PLAYERS_PATH = '/api/v1/players'
const TEAMS_PATH = '/api/v1/teams'

export interface PlayerListParams {
  page?: number
  pageSize?: number
  search?: string
  teamId?: string
  unassigned?: boolean
}

function playerPath(playerId: string) {
  return `${PLAYERS_PATH}/${encodeURIComponent(playerId)}`
}

export function fetchPlayers(
  params: PlayerListParams = {},
  signal?: AbortSignal,
) {
  if (params.teamId !== undefined && params.unassigned) {
    return Promise.reject(
      new Error('teamId and unassigned are mutually exclusive'),
    )
  }

  const query = new URLSearchParams()
  if (params.page !== undefined) query.set('page', String(params.page))
  if (params.pageSize !== undefined) {
    query.set('page_size', String(params.pageSize))
  }
  const normalizedSearch = params.search?.trim()
  if (normalizedSearch) query.set('search', normalizedSearch)
  if (params.teamId !== undefined) query.set('team_id', params.teamId)
  if (params.unassigned) query.set('unassigned', 'true')

  const queryString = query.toString()
  const path = queryString === '' ? PLAYERS_PATH : `${PLAYERS_PATH}?${queryString}`
  if (signal !== undefined) {
    return apiClient.request<PaginatedPlayerResponse>(path, { signal })
  }
  return apiClient.request<PaginatedPlayerResponse>(path)
}

export function fetchPlayer(playerId: string, signal?: AbortSignal) {
  const path = playerPath(playerId)
  if (signal !== undefined) {
    return apiClient.request<PlayerResponse>(path, { signal })
  }
  return apiClient.request<PlayerResponse>(path)
}

export function fetchTeamsForFilter(signal?: AbortSignal) {
  const request = apiClient.request<PaginatedTeamResponse>(
    `${TEAMS_PATH}?page_size=100`,
    signal === undefined ? undefined : { signal },
  )
  return request.then(({ teams }) =>
    teams.map(({ id, name }) => ({ id, name } satisfies TeamSummary)),
  )
}

export function createPlayer(payload: PlayerCreatePayload) {
  return apiClient.request<PlayerResponse>(PLAYERS_PATH, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updatePlayer(
  playerId: string,
  payload: PlayerUpdatePayload,
) {
  return apiClient.request<PlayerResponse>(playerPath(playerId), {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}
