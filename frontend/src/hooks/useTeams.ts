import { useCallback, useEffect, useState } from 'react'
import { fetchTeams } from '../api/teamApi'
import type { PaginatedTeamResponse } from '../types/team'

const PAGE_SIZE = 12

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError'
}

export default function useTeams() {
  const [page, setPage] = useState(1)
  const [result, setResult] = useState<PaginatedTeamResponse | null>(null)
  const [isFetching, setIsFetching] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    void fetchTeams({ page, pageSize: PAGE_SIZE }, controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) {
          setResult(response)
          setErrorMessage(null)
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && !isAbortError(error)) {
          setErrorMessage('Unable to load teams. Please try again.')
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsFetching(false)
      })
    return () => controller.abort()
  }, [page, retryKey])

  const retry = useCallback(() => {
    setErrorMessage(null)
    setIsFetching(true)
    setRetryKey((key) => key + 1)
  }, [])

  const changePage = useCallback((nextPage: number) => {
    if (nextPage < 1 || nextPage === page) return
    setErrorMessage(null)
    setIsFetching(true)
    setPage(nextPage)
  }, [page])

  return { errorMessage, isFetching, page, result, retry, setPage: changePage }
}
