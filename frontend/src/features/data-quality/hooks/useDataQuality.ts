import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiClientError } from '@shared/api/client'
import {
  applyDataQualityRemediation,
  fetchDataQuality,
  type DataQualityFinding,
  type DataQualityPageResponse,
  type DataQualityRemediationRequest,
  type DataQualityRemediationResult,
} from '../api/dataQualityApi'
import type {
  DataQualityFiltersState,
  DataQualityRemediationOutcome,
  DataQualityRemediationState,
  DataQualityRequestState,
} from '../types/dataQuality'

const DEFAULT_PAGE_SIZE = 20
const LOAD_ERROR = 'Unable to load data quality. Please try again.'
const REMEDIATION_ERROR = 'Unable to apply this remediation. No change was made.'
const REMEDIATION_CONFLICT =
  'This finding changed before the remediation was applied. Current findings were refreshed.'

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError'
}

function buildRemediationRequest(
  finding: DataQualityFinding,
): DataQualityRemediationRequest | null {
  const remediation = finding.direct_remediation
  if (remediation === null) return null

  switch (remediation.action) {
    case 'normalize_roster_order':
      return {
        finding_id: finding.finding_id,
        action: remediation.action,
        team_id: remediation.team_id,
        expected_team_version: remediation.expected_team_version,
        confirmed: true,
      }
    case 'remove_inactive_player':
      return {
        finding_id: finding.finding_id,
        action: remediation.action,
        team_id: remediation.team_id,
        player_id: remediation.player_id,
        expected_team_version: remediation.expected_team_version,
        confirmed: true,
      }
    case 'remove_inactive_assistant_assignment':
      return {
        finding_id: finding.finding_id,
        action: remediation.action,
        coach_id: remediation.coach_id,
        team_id: remediation.team_id,
        expected_coach_version: remediation.expected_coach_version,
        confirmed: true,
      }
  }
}

interface RemediationAttempt {
  outcome: DataQualityRemediationOutcome
  result?: DataQualityRemediationResult
}

export default function useDataQuality() {
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState<DataQualityFiltersState>({})
  const [retryKey, setRetryKey] = useState(0)
  const [result, setResult] = useState<DataQualityPageResponse | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [requestState, setRequestState] =
    useState<DataQualityRequestState>('loading')
  const [remediationState, setRemediationState] =
    useState<DataQualityRemediationState>('idle')
  const [remediationMessage, setRemediationMessage] = useState<string | null>(null)
  const latestRequest = useRef(0)
  const activeController = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    activeController.current?.abort()
    activeController.current = controller
    const requestId = ++latestRequest.current
    void fetchDataQuality(
      { page, pageSize: DEFAULT_PAGE_SIZE, ...filters },
      controller.signal,
    )
      .then((nextResult) => {
        if (requestId !== latestRequest.current) return
        setErrorMessage(null)
        setResult(nextResult)
        setRequestState('success')
      })
      .catch((error: unknown) => {
        if (isAbortError(error) || requestId !== latestRequest.current) return
        setErrorMessage(LOAD_ERROR)
        setRequestState('error')
      })

    return () => {
      controller.abort()
      if (activeController.current === controller) {
        activeController.current = null
      }
    }
  }, [filters, page, retryKey])

  const handlePageChange = useCallback((nextPage: number) => {
    setErrorMessage(null)
    setRequestState('refreshing')
    setPage(nextPage)
  }, [])
  const handleFilterChange = useCallback(
    (field: keyof DataQualityFiltersState, value: string) => {
      setErrorMessage(null)
      setRequestState(result === null ? 'loading' : 'refreshing')
      setFilters((current) => ({
        ...current,
        [field]: value === '' ? undefined : value,
      }))
      setPage(1)
    },
    [result],
  )
  const clearFilters = useCallback(() => {
    setErrorMessage(null)
    setRequestState(result === null ? 'loading' : 'refreshing')
    setFilters({})
    setPage(1)
  }, [result])
  const retry = useCallback(() => {
    setErrorMessage(null)
    setRequestState(result === null ? 'loading' : 'refreshing')
    setRetryKey((value) => value + 1)
  }, [result])
  const resetRemediation = useCallback(() => {
    setRemediationMessage(null)
    setRemediationState('idle')
  }, [])
  const remediate = useCallback(
    async (finding: DataQualityFinding): Promise<RemediationAttempt> => {
      const command = buildRemediationRequest(finding)
      if (command === null) {
        setRemediationMessage(REMEDIATION_ERROR)
        setRemediationState('error')
        return { outcome: 'failed' }
      }

      setRemediationMessage(null)
      setRemediationState('submitting')
      try {
        const remediationResult = await applyDataQualityRemediation(command)
        setErrorMessage(null)
        setRemediationState('idle')
        setRequestState(result === null ? 'loading' : 'refreshing')
        setRetryKey((value) => value + 1)
        return { outcome: 'applied', result: remediationResult }
      } catch (error: unknown) {
        if (error instanceof ApiClientError && error.status === 409) {
          setRemediationMessage(REMEDIATION_CONFLICT)
          setRemediationState('conflict')
          setRequestState(result === null ? 'loading' : 'refreshing')
          setRetryKey((value) => value + 1)
          return { outcome: 'conflict' }
        }
        setRemediationMessage(REMEDIATION_ERROR)
        setRemediationState('error')
        return { outcome: 'failed' }
      }
    },
    [result],
  )

  return {
    clearFilters,
    errorMessage,
    filters,
    handleFilterChange,
    handlePageChange,
    isFetching: requestState === 'loading' || requestState === 'refreshing',
    page,
    remediate,
    remediationMessage,
    remediationState,
    requestState,
    resetRemediation,
    result,
    retry,
  }
}
