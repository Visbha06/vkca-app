import { apiClient } from '@shared/api/client'
import type { DashboardResponse } from '../types/dashboard'

const DASHBOARD_PATH = '/api/v1/dashboard'

export function fetchDashboard(signal?: AbortSignal) {
  return apiClient.request<DashboardResponse>(
    DASHBOARD_PATH,
    signal === undefined ? undefined : { signal },
  )
}
