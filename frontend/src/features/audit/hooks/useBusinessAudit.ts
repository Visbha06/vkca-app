import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '@features/auth/context/AuthContext'
import { isAbortError } from '@shared/api/errors'
import {
  fetchBusinessAuditActors,
  fetchBusinessAuditEvents,
  fetchRecentBusinessAudit,
} from '../api/businessAuditApi'
import type {
  BusinessAuditActorOption,
  BusinessAuditFilters,
  BusinessAuditPageResponse,
  RecentBusinessAuditResponse,
} from '../types/businessAudit'

const BUSINESS_AUDIT_PAGE_SIZE = 20

export function hasBusinessAuditFilters(filters: BusinessAuditFilters) {
  return Object.values(filters).some(
    (value) => value !== undefined && value !== '',
  )
}

export function useBusinessAudit(initialFilters: BusinessAuditFilters = {}) {
  const [filters, setFilters] = useState(initialFilters)
  const [page, setPage] = useState(1)
  const [result, setResult] = useState<BusinessAuditPageResponse | null>(null)
  const [isFetching, setIsFetching] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)
  const requestId = useRef(0)

  useEffect(() => {
    const controller = new AbortController()
    const currentRequestId = requestId.current + 1
    requestId.current = currentRequestId

    void fetchBusinessAuditEvents(
      { ...filters, page, pageSize: BUSINESS_AUDIT_PAGE_SIZE },
      controller.signal,
    )
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
          setErrorMessage('Unable to load academy activity. Please try again.')
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
  }, [filters, page, retryKey])

  const updateFilters = useCallback((nextFilters: BusinessAuditFilters) => {
    setIsFetching(true)
    setErrorMessage(null)
    setFilters(nextFilters)
    setPage(1)
  }, [])

  const clearFilters = useCallback(() => updateFilters({}), [updateFilters])

  const changePage = useCallback(
    (nextPage: number) => {
      if (
        nextPage < 1 ||
        nextPage === page ||
        (result !== null && nextPage > Math.max(1, result.total_pages))
      ) {
        return
      }
      setIsFetching(true)
      setErrorMessage(null)
      setPage(nextPage)
    },
    [page, result],
  )

  const retry = useCallback(() => {
    setIsFetching(true)
    setErrorMessage(null)
    setRetryKey((current) => current + 1)
  }, [])

  return {
    changePage,
    clearFilters,
    errorMessage,
    filters,
    hasFilters: hasBusinessAuditFilters(filters),
    isFetching,
    isInitialLoading: isFetching && result === null,
    page,
    result,
    retry,
    updateFilters,
  }
}

export function useBusinessAuditActorOptions(enabled = true) {
  const { user } = useAuth()
  const canLoad = enabled && user?.role === 'head coach'
  const [actors, setActors] = useState<BusinessAuditActorOption[]>([])
  const [isLoading, setIsLoading] = useState(canLoad)
  const [hasLoaded, setHasLoaded] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    if (!canLoad) {
      return
    }

    const controller = new AbortController()
    void fetchBusinessAuditActors(controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) {
          setActors(response.actors)
          setErrorMessage(null)
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && !isAbortError(error)) {
          setErrorMessage('Unable to load actor options. Please try again.')
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setHasLoaded(true)
          setIsLoading(false)
        }
      })
    return () => controller.abort()
  }, [canLoad, retryKey])

  const retry = useCallback(() => {
    if (!canLoad) return
    setErrorMessage(null)
    setHasLoaded(false)
    setIsLoading(true)
    setRetryKey((current) => current + 1)
  }, [canLoad])

  return {
    actors: canLoad ? actors : [],
    errorMessage: canLoad ? errorMessage : null,
    isLoading: canLoad && (isLoading || !hasLoaded),
    retry,
  }
}

export function useRecentBusinessAudit(enabled = true) {
  const { user } = useAuth()
  const canLoad = enabled && user?.role === 'head coach'
  const [result, setResult] = useState<RecentBusinessAuditResponse | null>(null)
  const [isLoading, setIsLoading] = useState(canLoad)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)
  const requestId = useRef(0)

  useEffect(() => {
    if (!canLoad) {
      return
    }

    const controller = new AbortController()
    const currentRequestId = requestId.current + 1
    requestId.current = currentRequestId
    void fetchRecentBusinessAudit(4, controller.signal)
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
          setErrorMessage('Unable to load recent academy activity.')
        }
      })
      .finally(() => {
        if (
          !controller.signal.aborted &&
          requestId.current === currentRequestId
        ) {
          setIsLoading(false)
        }
      })

    return () => controller.abort()
  }, [canLoad, retryKey])

  const retry = useCallback(() => {
    if (!canLoad) return
    setErrorMessage(null)
    setIsLoading(true)
    setRetryKey((current) => current + 1)
  }, [canLoad])

  return {
    errorMessage: canLoad ? errorMessage : null,
    isLoading:
      canLoad && (isLoading || (result === null && errorMessage === null)),
    result: canLoad ? result : null,
    retry,
  }
}
