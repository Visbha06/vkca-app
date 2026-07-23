import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchPlayers, fetchTeamsForFilter } from '../api/playerApi'
import { useAuth } from '../auth/AuthContext'
import AddPlayerModal from '../components/AddPlayerModal'
import Pagination from '../components/Pagination'
import PlayerCardGrid from '../components/PlayerCardGrid'
import PlayerDetailsModal from '../components/PlayerDetailsModal'
import PlayersPageHeader from '../components/PlayersPageHeader'
import { UNASSIGNED_FILTER } from '../components/TeamFilter'
import type {
  PaginatedPlayerResponse,
  PlayerResponse,
  TeamSummary,
} from '../types/player'

const PAGE_SIZE = 20

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError'
}

export default function PlayersPage() {
  const { user } = useAuth()
  const canManagePlayers =
    user?.role === 'head coach' || user?.role === 'assistant coach'
  const [searchParams, setSearchParams] = useSearchParams()
  const [page, setPage] = useState(1)
  const [teamFilter, setTeamFilter] = useState<string | null>(null)
  const [teams, setTeams] = useState<TeamSummary[]>([])
  const [result, setResult] = useState<PaginatedPlayerResponse | null>(null)
  const [selectedPlayer, setSelectedPlayer] = useState<PlayerResponse | null>(null)
  const [isAddPlayerOpen, setIsAddPlayerOpen] = useState(
    () => canManagePlayers && searchParams.get('action') === 'add',
  )
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)
  const [refreshKey, setRefreshKey] = useState(0)
  const listRegionRef = useRef<HTMLDivElement>(null)
  const focusListAfterLoadRef = useRef(false)
  useEffect(() => {
    if (searchParams.get('action') !== 'add') return
    const nextParams = new URLSearchParams(searchParams)
    nextParams.delete('action')
    setSearchParams(nextParams, { replace: true })
  }, [searchParams, setSearchParams])
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
    const controller = new AbortController()

    const params = {
      page,
      pageSize: PAGE_SIZE,
      ...(teamFilter === UNASSIGNED_FILTER
        ? { unassigned: true }
        : teamFilter === null
          ? {}
          : { teamId: teamFilter }),
    }

    void fetchPlayers(params, controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) setResult(response)
      })
      .catch((error: unknown) => {
        if (!isAbortError(error) && !controller.signal.aborted) {
          setResult(null)
          setErrorMessage('Unable to load players. Please try again.')
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false)
      })

    return () => controller.abort()
  }, [page, refreshKey, retryKey, teamFilter])

  useEffect(() => {
    if (!isLoading && focusListAfterLoadRef.current) {
      focusListAfterLoadRef.current = false
      listRegionRef.current?.focus()
    }
  }, [isLoading])

  function handleFilterChange(nextFilter: string | null) {
    setIsLoading(true)
    setErrorMessage(null)
    setTeamFilter(nextFilter)
    setPage(1)
  }

  function handlePageChange(nextPage: number) {
    if (nextPage === page || nextPage < 1) return
    focusListAfterLoadRef.current = true
    setIsLoading(true)
    setErrorMessage(null)
    setPage(nextPage)
  }

  function handleRetry() {
    setIsLoading(true)
    setErrorMessage(null)
    setRetryKey((key) => key + 1)
  }

  function handlePlayerCreated(player: PlayerResponse) {
    setSuccessMessage(
      `${player.first_name} ${player.last_name} was added successfully.`,
    )
    setRefreshKey((key) => key + 1)
  }

  const emptyMessage =
    teamFilter === null
      ? 'No active players are available.'
      : 'No players match this team filter.'

  return (
    <section className="mx-auto w-full max-w-7xl">
      <PlayersPageHeader
        canManagePlayers={canManagePlayers}
        isLoading={isLoading}
        teams={teams}
        teamFilter={teamFilter}
        totalPlayers={result?.total_players}
        onAdd={() => setIsAddPlayerOpen(true)}
        onFilterChange={handleFilterChange}
      />

      {successMessage ? (
        <p role="status" className="mb-6 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm font-semibold text-emerald-950">
          {successMessage}
        </p>
      ) : null}

      <div ref={listRegionRef} tabIndex={-1} className="focus:outline-none">
        {errorMessage !== null ? (
          <div
            role="alert"
            className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-950 sm:p-6"
          >
            <p className="font-semibold">{errorMessage}</p>
            <button
              type="button"
              className="mt-4 inline-flex min-h-11 items-center rounded-lg border border-red-800 px-4 text-sm font-semibold transition-colors hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2"
              onClick={handleRetry}
            >
              Retry
            </button>
          </div>
        ) : (
          <PlayerCardGrid
            players={result?.players ?? []}
            isLoading={isLoading}
            emptyMessage={emptyMessage}
            onSelect={setSelectedPlayer}
          />
        )}
      </div>

      {errorMessage === null && result !== null && result.total_pages > 1 ? (
        <div className="mt-8 border-t border-slate-200 pt-6">
          <Pagination
            page={result.page}
            totalPages={result.total_pages}
            isLoading={isLoading}
            onPageChange={handlePageChange}
          />
        </div>
      ) : null}

      {selectedPlayer !== null ? (
        <PlayerDetailsModal
          player={selectedPlayer}
          onClose={() => setSelectedPlayer(null)}
        />
      ) : null}

      {isAddPlayerOpen ? (
        <AddPlayerModal
          onClose={() => setIsAddPlayerOpen(false)}
          onCreated={handlePlayerCreated}
        />
      ) : null}
    </section>
  )
}
