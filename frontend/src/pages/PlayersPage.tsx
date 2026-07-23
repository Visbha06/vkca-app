import { useEffect, useRef, useState } from 'react'
import { fetchPlayers, fetchTeamsForFilter } from '../api/playerApi'
import { useAuth } from '../auth/AuthContext'
import Pagination from '../components/Pagination'
import PlayerCardGrid from '../components/PlayerCardGrid'
import PlayerDetailsModal from '../components/PlayerDetailsModal'
import TeamFilter, { UNASSIGNED_FILTER } from '../components/TeamFilter'
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
  const [page, setPage] = useState(1)
  const [teamFilter, setTeamFilter] = useState<string | null>(null)
  const [teams, setTeams] = useState<TeamSummary[]>([])
  const [result, setResult] = useState<PaginatedPlayerResponse | null>(null)
  const [selectedPlayer, setSelectedPlayer] = useState<PlayerResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)
  const listRegionRef = useRef<HTMLDivElement>(null)
  const focusListAfterLoadRef = useRef(false)

  const canManagePlayers =
    user?.role === 'head coach' || user?.role === 'assistant coach'

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
  }, [page, retryKey, teamFilter])

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

  const emptyMessage =
    teamFilter === null
      ? 'No active players are available.'
      : 'No players match this team filter.'

  return (
    <section className="mx-auto w-full max-w-7xl">
      <header className="flex flex-col gap-5 border-b border-slate-200 pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 md:text-4xl" tabIndex={-1}>
            Player Directory
          </h1>
          <p className="mt-2 max-w-2xl text-base leading-7 text-slate-600">
            Browse active players, team membership, and playing profiles.
          </p>
        </div>
        {canManagePlayers ? (
          <button
            type="button"
            disabled
            className="inline-flex min-h-11 items-center justify-center rounded-lg border border-slate-200 bg-slate-100 px-4 text-sm font-semibold text-slate-500"
            title="Player creation is not available yet"
          >
            Add Player
          </button>
        ) : null}
      </header>

      <div className="flex flex-col gap-5 py-6 sm:flex-row sm:items-end sm:justify-between">
        <TeamFilter
          teams={teams}
          value={teamFilter}
          disabled={isLoading}
          onChange={handleFilterChange}
        />
        {result !== null && result.total_players > 0 ? (
          <p className="text-sm font-medium text-slate-600">
            {result.total_players} active {result.total_players === 1 ? 'player' : 'players'}
          </p>
        ) : null}
      </div>

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
    </section>
  )
}
