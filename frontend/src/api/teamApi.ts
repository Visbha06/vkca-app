import { apiClient } from './client'
import type {
  PaginatedTeamResponse,
  TeamCreatePayload,
  TeamResponse,
  TeamRosterResponse,
  TeamUpdatePayload,
} from '../types/team'

const TEAMS_PATH = '/api/v1/teams'

export interface TeamListParams {
  page?: number
  pageSize?: number
}

function teamPath(teamId: string) {
  return `${TEAMS_PATH}/${encodeURIComponent(teamId)}`
}

export function fetchTeams(params: TeamListParams = {}, signal?: AbortSignal) {
  const query = new URLSearchParams()
  if (params.page !== undefined) query.set('page', String(params.page))
  if (params.pageSize !== undefined) {
    query.set('page_size', String(params.pageSize))
  }
  const queryString = query.toString()
  const path = queryString === '' ? TEAMS_PATH : `${TEAMS_PATH}?${queryString}`
  return apiClient.request<PaginatedTeamResponse>(
    path,
    signal === undefined ? undefined : { signal },
  )
}

export function createTeam(payload: TeamCreatePayload) {
  return apiClient.request<TeamResponse>(TEAMS_PATH, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateTeam(teamId: string, payload: TeamUpdatePayload) {
  return apiClient.request<TeamResponse>(teamPath(teamId), {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function fetchTeamRoster(teamId: string, signal?: AbortSignal) {
  return apiClient.request<TeamRosterResponse>(
    `${teamPath(teamId)}/players`,
    signal === undefined ? undefined : { signal },
  )
}
