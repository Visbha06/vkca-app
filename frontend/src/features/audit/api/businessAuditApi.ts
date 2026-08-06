import { apiClient } from '@shared/api/client'
import type {
  BusinessAuditActorOptionsResponse,
  BusinessAuditListParams,
  BusinessAuditPageResponse,
  RecentBusinessAuditResponse,
} from '../types/businessAudit'

const BUSINESS_AUDIT_PATH = '/api/v1/audit-log'
const MAX_PAGE_SIZE = 100
const MAX_RECENT_LIMIT = 4

function addQueryValue(
  query: URLSearchParams,
  key: string,
  value: string | number | undefined,
) {
  if (value !== undefined && value !== '') query.set(key, String(value))
}

export function fetchBusinessAuditEvents(
  params: BusinessAuditListParams = {},
  signal?: AbortSignal,
) {
  if (params.page !== undefined && params.page < 1) {
    return Promise.reject(new Error('page must be greater than or equal to 1'))
  }
  if (
    params.pageSize !== undefined &&
    (params.pageSize < 1 || params.pageSize > MAX_PAGE_SIZE)
  ) {
    return Promise.reject(new Error('pageSize must be between 1 and 100'))
  }

  const query = new URLSearchParams()
  addQueryValue(query, 'page', params.page)
  addQueryValue(query, 'page_size', params.pageSize)
  addQueryValue(query, 'actor_user_id', params.actorUserId)
  addQueryValue(query, 'action_category', params.actionCategory)
  addQueryValue(query, 'action_type', params.actionType)
  addQueryValue(query, 'entity_type', params.entityType)
  addQueryValue(query, 'target_entity_id', params.targetEntityId)
  addQueryValue(query, 'start_date', params.startDate)
  addQueryValue(query, 'end_date', params.endDate)

  const queryString = query.toString()
  const path =
    queryString === '' ? BUSINESS_AUDIT_PATH : `${BUSINESS_AUDIT_PATH}?${queryString}`
  return apiClient.request<BusinessAuditPageResponse>(
    path,
    signal === undefined ? undefined : { signal },
  )
}

export function fetchRecentBusinessAudit(
  limit = MAX_RECENT_LIMIT,
  signal?: AbortSignal,
) {
  if (!Number.isInteger(limit) || limit < 1 || limit > MAX_RECENT_LIMIT) {
    return Promise.reject(new Error('recent audit limit must be between 1 and 4'))
  }
  return apiClient.request<RecentBusinessAuditResponse>(
    `${BUSINESS_AUDIT_PATH}/recent?limit=${limit}`,
    signal === undefined ? undefined : { signal },
  )
}

export function fetchBusinessAuditActors(signal?: AbortSignal) {
  return apiClient.request<BusinessAuditActorOptionsResponse>(
    `${BUSINESS_AUDIT_PATH}/actors`,
    signal === undefined ? undefined : { signal },
  )
}
