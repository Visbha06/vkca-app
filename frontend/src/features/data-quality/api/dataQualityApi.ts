import { apiClient } from '@shared/api/client'
import type { components } from './generated'

export type DataQualityPageResponse =
  components['schemas']['DataQualityPageResponse']
export type DataQualityFinding = components['schemas']['DataQualityFinding']
export type DataQualityRemediationRequest =
  | components['schemas']['NormalizeRosterOrderRequest']
  | components['schemas']['RemoveInactivePlayerRequest']
  | components['schemas']['RemoveInactiveAssistantAssignmentRequest']
export type DataQualityRemediationResult =
  components['schemas']['DataQualityRemediationResult']

export interface DataQualityRequest {
  page?: number
  pageSize?: number
  severity?: components['schemas']['QualitySeverity']
  domain?: components['schemas']['QualityDomain']
  ruleId?: components['schemas']['QualityRuleId']
}

const DATA_QUALITY_PATH = '/api/v1/data-quality'
const DATA_QUALITY_REMEDIATION_PATH = `${DATA_QUALITY_PATH}/remediations`

export async function fetchDataQuality(
  request: DataQualityRequest = {},
  signal?: AbortSignal,
): Promise<DataQualityPageResponse> {
  const parameters = new URLSearchParams()
  if (request.page !== undefined) parameters.set('page', String(request.page))
  if (request.pageSize !== undefined) {
    parameters.set('page_size', String(request.pageSize))
  }
  if (request.severity !== undefined) parameters.set('severity', request.severity)
  if (request.domain !== undefined) parameters.set('domain', request.domain)
  if (request.ruleId !== undefined) parameters.set('rule_id', request.ruleId)
  const query = parameters.toString()

  return apiClient.request<DataQualityPageResponse>(
    query ? `${DATA_QUALITY_PATH}?${query}` : DATA_QUALITY_PATH,
    { signal },
  )
}

export async function applyDataQualityRemediation(
  request: DataQualityRemediationRequest,
): Promise<DataQualityRemediationResult> {
  return apiClient.request<DataQualityRemediationResult>(
    DATA_QUALITY_REMEDIATION_PATH,
    {
      method: 'POST',
      body: JSON.stringify(request),
    },
  )
}
