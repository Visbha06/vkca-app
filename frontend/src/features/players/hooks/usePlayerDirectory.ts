import { useEffect, useRef, useState } from 'react'
import { fetchPlayers, fetchTeamsForFilter } from '../api/playerApi'
import { UNASSIGNED_FILTER } from '../components/player-directory/TeamFilter'
import type {
  PaginatedPlayerResponse,
  PlayerResponse,
  TeamSummary,
} from '../types/player'

const PAGE_SIZE = 20

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError'
}

export default function usePlayerDirectory() {
  const [page, setPage] = useState(1)
  const [searchQuery, setSearchQuery] = useState('')
  const [committedSearch, setCommittedSearch] = useState('')
  const [teamFilter, setTeamFilter] = useState<string | null>(null)
  const [teams, setTeams] = useState<TeamSummary[]>([])
  const [result, setResult] = useState<PaginatedPlayerResponse | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [isFetching, setIsFetching] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)
  const [refreshKey, setRefreshKey] = useState(0)
  const searchInputRef = useRef<HTMLInputElement>(null)
  const listRegionRef = useRef<HTMLDivElement>(null)
  const focusListAfterLoadRef = useRef(false)

  useEffect(() => {
    const controller = new AbortController()
    void fetchTeamsForFilter(controller.signal)
      .then((teamOptions) => {
        if (!controller.signal.aborted) setTeams(teamOptions)
      })
      .catch((error: unknown) => {
        if (!isAbortError(error)) setTeams([])
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const normalizedSearch = searchQuery.trim()
    if (normalizedSearch === committedSearch) return

    const debounceTimer = window.setTimeout(() => {
      setIsFetching(true)
      setErrorMessage(null)
      setCommittedSearch(normalizedSearch)
      setPage(1)
    }, 275)

    return () => window.clearTimeout(debounceTimer)
  }, [committedSearch, searchQuery])

  useEffect(() => {
    const controller = new AbortController()
    const params = {
      page,
      pageSize: PAGE_SIZE,
      ...(committedSearch === '' ? {} : { search: committedSearch }),
      ...(teamFilter === UNASSIGNED_FILTER
        ? { unassigned: true }
        : teamFilter === null
          ? {}
          : { teamId: teamFilter }),
    }
    void fetchPlayers(params, controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) {
          setResult(response)
          setErrorMessage(null)
        }
      })
      .catch((error: unknown) => {
        if (!isAbortError(error) && !controller.signal.aborted) {
          setErrorMessage('Unable to load players. Please try again.')
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsFetching(false)
      })
    return () => controller.abort()
  }, [committedSearch, page, refreshKey, retryKey, teamFilter])

  useEffect(() => {
    if (!isFetching && focusListAfterLoadRef.current) {
      focusListAfterLoadRef.current = false
      listRegionRef.current?.focus()
    }
  }, [isFetching])

  function handleFilterChange(nextFilter: string | null) {
    setIsFetching(true)
    setErrorMessage(null)
    setTeamFilter(nextFilter)
    setPage(1)
  }

  function handleClearSearch() {
    searchInputRef.current?.focus()
    setIsFetching(true)
    setSearchQuery('')
    setCommittedSearch('')
    setPage(1)
    setErrorMessage(null)
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

  function handlePlayerMutation(
    player: PlayerResponse,
    action: 'added' | 'updated',
  ) {
    setSuccessMessage(
      `${player.first_name} ${player.last_name} was ${action} successfully.`,
    )
    setIsFetching(true)
    setErrorMessage(null)
    setRefreshKey((key) => key + 1)
  }

  return {
    committedSearch,
    errorMessage,
    handleClearSearch,
    handleFilterChange,
    handlePageChange,
    handlePlayerMutation,
    handleRetry,
    isFetching,
    listRegionRef,
    result,
    searchInputRef,
    searchQuery,
    setSearchQuery,
    successMessage,
    teamFilter,
    teams,
  }
}
