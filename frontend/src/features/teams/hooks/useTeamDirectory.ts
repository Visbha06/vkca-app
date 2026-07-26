import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchTeams } from '../api/teamApi'
import type { AgeGroup, PaginatedTeamResponse } from '../types/team'

const PAGE_SIZE = 12

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError'
}

export default function useTeamDirectory() {
  const [page, setPage] = useState(1)
  const [result, setResult] = useState<PaginatedTeamResponse | null>(null)
  const [isFetching, setIsFetching] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)
  const [searchQuery, setSearchQuery] = useState('')
  const [ageGroupFilter, setAgeGroupFilter] = useState<AgeGroup | null>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)

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

  const ageGroups = useMemo(
    () =>
      Array.from(new Set(result?.teams.map(({ age_group }) => age_group) ?? []))
        .sort(),
    [result],
  )
  const filteredTeams = useMemo(() => {
    const search = searchQuery.trim().toLocaleLowerCase()
    return (result?.teams ?? []).filter(
      (team) =>
        (search === '' || team.name.toLocaleLowerCase().includes(search)) &&
        (ageGroupFilter === null || team.age_group === ageGroupFilter),
    )
  }, [ageGroupFilter, result, searchQuery])

  function clearFilters() {
    setSearchQuery('')
    setAgeGroupFilter(null)
    searchInputRef.current?.focus()
  }

  return {
    ageGroupFilter,
    ageGroups,
    clearFilters,
    errorMessage,
    filteredTeams,
    isFetching,
    page,
    result,
    retry,
    searchInputRef,
    searchQuery,
    setAgeGroupFilter,
    setPage: changePage,
    setSearchQuery,
  }
}
