import { useEffect, useRef, useState } from 'react'
import { fetchCoaches } from '../api/coachApi'
import type {
  CoachStatusFilterValue,
  PaginatedCoachResponse,
} from '../types/coach'

const PAGE_SIZE = 12

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError'
}

export default function useCoachDirectory() {
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState<CoachStatusFilterValue>('active')
  const [result, setResult] = useState<PaginatedCoachResponse | null>(null)
  const [isFetching, setIsFetching] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const listRegionRef = useRef<HTMLDivElement>(null)
  const focusListAfterLoadRef = useRef(false)

  useEffect(() => {
    const controller = new AbortController()
    void fetchCoaches({ status, page, pageSize: PAGE_SIZE }, controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) {
          setResult(response)
          setErrorMessage(null)
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && !isAbortError(error)) {
          setErrorMessage('Unable to load coaches. Please try again.')
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsFetching(false)
      })
    return () => controller.abort()
  }, [page, retryKey, status])

  useEffect(() => {
    if (!isFetching && focusListAfterLoadRef.current) {
      focusListAfterLoadRef.current = false
      listRegionRef.current?.focus()
    }
  }, [isFetching])

  function handleFilterChange(nextStatus: CoachStatusFilterValue) {
    setIsFetching(true)
    setErrorMessage(null)
    setStatus(nextStatus)
    setPage(1)
  }

  function handlePageChange(nextPage: number) {
    if (nextPage === page || nextPage < 1) return
    focusListAfterLoadRef.current = true
    setIsFetching(true)
    setErrorMessage(null)
    setPage(nextPage)
  }

  function handleRetry() {
    setIsFetching(true)
    setErrorMessage(null)
    setRetryKey((key) => key + 1)
  }

  return {
    errorMessage,
    handleFilterChange,
    handlePageChange,
    handleRetry,
    isFetching,
    listRegionRef,
    result,
    status,
    successMessage,
    setSuccessMessage,
  }
}
