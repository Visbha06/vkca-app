import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchDataQuality, type DataQualityPageResponse } from '../api/dataQualityApi'
import type {
  DataQualityFiltersState,
  DataQualityRequestState,
} from '../types/dataQuality'

const DEFAULT_PAGE_SIZE = 20
const LOAD_ERROR = 'Unable to load data quality. Please try again.'

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError'
}

export default function useDataQuality() {
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState<DataQualityFiltersState>({})
  const [retryKey, setRetryKey] = useState(0)
  const [result, setResult] = useState<DataQualityPageResponse | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [requestState, setRequestState] =
    useState<DataQualityRequestState>('loading')
  const latestRequest = useRef(0)

  useEffect(() => {
    const controller = new AbortController()
    const requestId = ++latestRequest.current
    void fetchDataQuality(
      { page, pageSize: DEFAULT_PAGE_SIZE, ...filters },
      controller.signal,
    )
      .then((nextResult) => {
        if (requestId !== latestRequest.current) return
        setResult(nextResult)
        setRequestState('success')
      })
      .catch((error: unknown) => {
        if (isAbortError(error) || requestId !== latestRequest.current) return
        setErrorMessage(LOAD_ERROR)
        setRequestState('error')
      })

    return () => controller.abort()
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

  return {
    clearFilters,
    errorMessage,
    filters,
    handleFilterChange,
    handlePageChange,
    isFetching: requestState === 'loading' || requestState === 'refreshing',
    page,
    requestState,
    result,
    retry,
  }
}
