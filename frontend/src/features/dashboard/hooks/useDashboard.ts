import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchDashboard } from '../api/dashboardApi'
import type { DashboardResponse } from '../types/dashboard'

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError'
}

export function useDashboard() {
  const [result, setResult] = useState<DashboardResponse | null>(null)
  const [isFetching, setIsFetching] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)
  const requestId = useRef(0)

  useEffect(() => {
    const controller = new AbortController()
    const currentRequestId = requestId.current + 1
    requestId.current = currentRequestId

    void fetchDashboard(controller.signal)
      .then((response) => {
        if (
          !controller.signal.aborted &&
          requestId.current === currentRequestId
        ) {
          setResult(response)
          setErrorMessage(null)
        }
      })
      .catch((error: unknown) => {
        if (
          !controller.signal.aborted &&
          requestId.current === currentRequestId &&
          !isAbortError(error)
        ) {
          setErrorMessage('Unable to load or refresh your dashboard.')
        }
      })
      .finally(() => {
        if (
          !controller.signal.aborted &&
          requestId.current === currentRequestId
        ) {
          setIsFetching(false)
        }
      })

    return () => controller.abort()
  }, [retryKey])

  const retry = useCallback(() => {
    setErrorMessage(null)
    setIsFetching(true)
    setRetryKey((current) => current + 1)
  }, [])

  return {
    errorMessage,
    isFetching,
    isInitialLoading: isFetching && result === null,
    result,
    retry,
  }
}
