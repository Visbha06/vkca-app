import { apiClient } from '@shared/api/client'
import type {
  CoachCreatePayload,
  CoachCreateResponse,
  CoachResponse,
  CoachStatusResponse,
  CoachStatusFilterValue,
  CoachTeamUpdatePayload,
  PaginatedCoachResponse,
} from '../types/coach'

const COACHES_PATH = '/api/v1/coaches'

export interface CoachListParams {
  status?: CoachStatusFilterValue
  page?: number
  pageSize?: number
}

export function fetchCoachDetails(coachId: string, signal?: AbortSignal) {
  const path = `${COACHES_PATH}/${encodeURIComponent(coachId)}`
  return apiClient.request<CoachResponse>(
    path,
    signal === undefined ? undefined : { signal },
  )
}

export function fetchCoaches(
  params: CoachListParams = {},
  signal?: AbortSignal,
) {
  const query = new URLSearchParams()
  if (params.status !== undefined) query.set('status', params.status)
  if (params.page !== undefined) query.set('page', String(params.page))
  if (params.pageSize !== undefined) {
    query.set('page_size', String(params.pageSize))
  }
  const queryString = query.toString()
  const path = queryString === '' ? COACHES_PATH : `${COACHES_PATH}?${queryString}`
  return apiClient.request<PaginatedCoachResponse>(
    path,
    signal === undefined ? undefined : { signal },
  )
}

export function createCoach(payload: CoachCreatePayload) {
  return apiClient.request<CoachCreateResponse>(COACHES_PATH, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

function updateCoachStatus(
  coachId: string,
  action: 'disable' | 'reactivate',
  versionNumber: number,
) {
  return apiClient.request<CoachStatusResponse>(
    `/api/v1/users/${encodeURIComponent(coachId)}/${action}`,
    {
      method: 'POST',
      body: JSON.stringify({ version_number: versionNumber }),
    },
  )
}

export function deactivateCoach(coachId: string, versionNumber: number) {
  return updateCoachStatus(coachId, 'disable', versionNumber)
}

export function reactivateCoach(coachId: string, versionNumber: number) {
  return updateCoachStatus(coachId, 'reactivate', versionNumber)
}

export function updateTeamAssignments(
  coachId: string,
  payload: CoachTeamUpdatePayload,
) {
  return apiClient.request<CoachResponse>(
    `${COACHES_PATH}/${encodeURIComponent(coachId)}/teams`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
  )
}
