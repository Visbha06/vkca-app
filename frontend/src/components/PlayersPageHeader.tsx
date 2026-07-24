import type { TeamSummary } from '../types/player'
import PlayerSearchField from './PlayerSearchField'
import TeamFilter from './TeamFilter'

interface PlayersPageHeaderProps {
  canManagePlayers: boolean
  hasActiveFilters: boolean
  isFetching: boolean
  searchQuery: string
  teams: TeamSummary[]
  teamFilter: string | null
  totalPlayers?: number
  onAdd: () => void
  onFilterChange: (filter: string | null) => void
  onSearchChange: (query: string) => void
}

export default function PlayersPageHeader({
  canManagePlayers,
  hasActiveFilters,
  isFetching,
  searchQuery,
  teams,
  teamFilter,
  totalPlayers,
  onAdd,
  onFilterChange,
  onSearchChange,
}: PlayersPageHeaderProps) {
  const countCopy =
    totalPlayers === undefined
      ? null
      : hasActiveFilters
        ? `${totalPlayers} ${totalPlayers === 1 ? 'player' : 'players'} found`
        : `${totalPlayers} active ${totalPlayers === 1 ? 'player' : 'players'}`

  return (
    <>
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
            className="inline-flex min-h-11 items-center justify-center rounded-lg border border-academy bg-white px-4 text-sm font-semibold text-slate-900 transition-colors hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
            onClick={onAdd}
          >
            Add Player
          </button>
        ) : null}
      </header>

      <div className="flex flex-col gap-4 py-6 sm:flex-row sm:flex-wrap sm:items-end">
        <PlayerSearchField value={searchQuery} onChange={onSearchChange} />
        <TeamFilter
          teams={teams}
          value={teamFilter}
          disabled={false}
          onChange={onFilterChange}
        />
        {countCopy !== null ? (
          <p
            aria-atomic="true"
            aria-live="polite"
            className="min-h-5 text-sm font-medium text-slate-600 sm:basis-full lg:mb-3 lg:ml-auto lg:basis-auto"
          >
            <span className="sr-only">{isFetching ? 'Updating results. ' : ''}</span>
            {countCopy}
          </p>
        ) : null}
      </div>
    </>
  )
}
