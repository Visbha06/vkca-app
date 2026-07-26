import type { RefObject } from 'react'
import type {
  PaginatedPlayerResponse,
  PlayerResponse,
} from '../../types/player'
import Pagination from '@shared/components/navigation/Pagination'
import PlayerCardGrid from './PlayerCardGrid'

interface PlayerDirectoryResultsProps {
  canManagePlayers: boolean
  errorMessage: string | null
  isFetching: boolean
  listRegionRef: RefObject<HTMLDivElement | null>
  result: PaginatedPlayerResponse | null
  search: string
  teamFilter: string | null
  onAddPlayer: () => void
  onClearSearch: () => void
  onPageChange: (page: number) => void
  onRetry: () => void
  onSelectPlayer: (player: PlayerResponse) => void
}

const retryButtonClass =
  'inline-flex min-h-11 items-center justify-center rounded-lg border border-red-800 px-4 text-sm font-semibold transition-colors hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2'

function getEmptyState(search: string, hasTeamFilter: boolean) {
  if (search !== '') {
    return hasTeamFilter
      ? {
          description:
            'Clear the search or choose another team to broaden the results.',
          message: `No players match “${search}” and this team filter.`,
        }
      : {
          description:
            'Check the spelling or clear the search to view all active players.',
          message: `No players found for “${search}”.`,
        }
  }

  return hasTeamFilter
    ? {
        description: 'Choose another team or view all players.',
        message: 'No players match this team filter.',
      }
    : {
        description:
          'Add the first player profile to begin building the active directory.',
        message: 'No active players are available.',
      }
}

export default function PlayerDirectoryResults({
  canManagePlayers,
  errorMessage,
  isFetching,
  listRegionRef,
  result,
  search,
  teamFilter,
  onAddPlayer,
  onClearSearch,
  onPageChange,
  onRetry,
  onSelectPlayer,
}: PlayerDirectoryResultsProps) {
  const hasInitialError = errorMessage !== null && result === null
  const hasSearch = search !== ''
  const hasTeamFilter = teamFilter !== null
  const emptyState = getEmptyState(search, hasTeamFilter)

  return (
    <>
      <div
        ref={listRegionRef}
        aria-busy={isFetching}
        tabIndex={-1}
        className="focus:outline-none"
      >
        {hasInitialError ? (
          <div
            role="alert"
            className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-950 sm:p-6"
          >
            <p className="font-semibold">{errorMessage}</p>
            <button
              type="button"
              className={`${retryButtonClass} mt-4`}
              onClick={onRetry}
            >
              Retry
            </button>
          </div>
        ) : (
          <>
            {errorMessage !== null ? (
              <div
                role="alert"
                className="mb-4 flex flex-col gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-red-950 sm:flex-row sm:items-center sm:justify-between"
              >
                <p className="text-sm font-semibold">
                  Unable to update the player results. Previous results are
                  still shown.
                </p>
                <button
                  type="button"
                  className={`${retryButtonClass} shrink-0 self-start sm:self-auto`}
                  onClick={onRetry}
                >
                  Retry
                </button>
              </div>
            ) : null}
            <PlayerCardGrid
              players={result?.players ?? []}
              showSkeletons={isFetching && result === null}
              emptyMessage={emptyState.message}
              emptyDescription={emptyState.description}
              emptyActionLabel={
                hasSearch
                  ? 'Clear search'
                  : canManagePlayers && !hasTeamFilter
                    ? 'Add your first player'
                    : undefined
              }
              emptyActionVariant={hasSearch ? 'secondary' : 'primary'}
              onEmptyAction={hasSearch ? onClearSearch : onAddPlayer}
              onSelect={onSelectPlayer}
            />
          </>
        )}
      </div>

      {result !== null && result.total_pages > 1 ? (
        <div className="mt-8 border-t border-slate-200 pt-6">
          <Pagination
            ariaLabel="Player pages"
            page={result.page}
            totalPages={result.total_pages}
            isLoading={isFetching}
            onPageChange={onPageChange}
          />
        </div>
      ) : null}
    </>
  )
}
