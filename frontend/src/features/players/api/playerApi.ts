import { apiClient } from '@shared/api/client'
import type {
  PaginatedPlayerResponse,
  PaginatedPlayerAccountResponse,
  PlayerAccountAssociationResponse,
  PlayerAccountLinkPayload,
  PlayerAccountLookupParams,
  PlayerAccountReassignPayload,
  PlayerAccountUnlinkPayload,
  PlayerCreatePayload,
  PlayerResponse,
  PlayerUpdatePayload,
  TeamSummary,
} from '../types/player'

interface TeamFilterResponse {
  teams: TeamSummary[]
}

const PLAYERS_PATH = '/api/v1/players'
const TEAMS_PATH = '/api/v1/teams'
const PLAYER_ACCOUNT_LOOKUP_PATH = `${PLAYERS_PATH}/account-linking/users`

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
  const request = apiClient.request<TeamFilterResponse>(
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

function accountPath(playerId: string) {
  return `${playerPath(playerId)}/account`
}

export function fetchEligiblePlayerAccounts(
  params: PlayerAccountLookupParams = {},
  signal?: AbortSignal,
) {
  const query = new URLSearchParams()
  const search = params.search?.trim()
  if (search) query.set('search', search)
  if (params.page !== undefined) query.set('page', String(params.page))
  if (params.pageSize !== undefined) {
    query.set('page_size', String(params.pageSize))
  }
  const queryString = query.toString()
  const path = queryString
    ? `${PLAYER_ACCOUNT_LOOKUP_PATH}?${queryString}`
    : PLAYER_ACCOUNT_LOOKUP_PATH
  return apiClient.request<PaginatedPlayerAccountResponse>(
    path,
    signal === undefined ? undefined : { signal },
  )
}

export function fetchPlayerAccountAssociation(
  playerId: string,
  signal?: AbortSignal,
) {
  return apiClient.request<PlayerAccountAssociationResponse>(
    accountPath(playerId),
    signal === undefined ? undefined : { signal },
  )
}

export function linkPlayerAccount(
  playerId: string,
  payload: PlayerAccountLinkPayload,
) {
  return apiClient.request<PlayerAccountAssociationResponse>(
    accountPath(playerId),
    { method: 'PUT', body: JSON.stringify(payload) },
  )
}

export function unlinkPlayerAccount(
  playerId: string,
  payload: PlayerAccountUnlinkPayload,
) {
  return apiClient.request<PlayerAccountAssociationResponse>(
    accountPath(playerId),
    { method: 'DELETE', body: JSON.stringify(payload) },
  )
}

export function reassignPlayerAccount(
  playerId: string,
  payload: PlayerAccountReassignPayload,
) {
  return apiClient.request<PlayerAccountAssociationResponse>(
    `${accountPath(playerId)}/reassign`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}
