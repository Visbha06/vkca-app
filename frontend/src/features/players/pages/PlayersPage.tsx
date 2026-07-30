import { useState } from 'react'
import { useAuth } from '@features/auth'
import SuccessToast from '@shared/components/feedback/SuccessToast'
import PlayerDirectoryResults from '../components/player-directory/PlayerDirectoryResults'
import PlayersPageHeader from '../components/player-directory/PlayersPageHeader'
import PlayersPageModals from '../components/PlayersPageModals'
import useInitialAddPlayerAction from '../hooks/useInitialAddPlayerAction'
import usePlayerDirectory from '../hooks/usePlayerDirectory'
import type { PlayerResponse } from '../types/player'

export default function PlayersPage() {
  const { user } = useAuth()
  const canManagePlayers =
    user?.role === 'head coach' || user?.role === 'assistant coach'
  const shouldOpenAddPlayer = useInitialAddPlayerAction(canManagePlayers)
  const {
    committedSearch,
    dismissSuccessToast,
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
    successToast,
    teamFilter,
    teams,
  } = usePlayerDirectory()
  const [selectedPlayer, setSelectedPlayer] =
    useState<PlayerResponse | null>(null)
  const [isAddPlayerOpen, setIsAddPlayerOpen] = useState(
    shouldOpenAddPlayer,
  )
  const hasSearch = committedSearch !== ''
  const hasTeamFilter = teamFilter !== null
  const hasActiveFilters = hasSearch || hasTeamFilter

  return (
    <section className="mx-auto w-full max-w-7xl">
      <PlayersPageHeader
        canManagePlayers={canManagePlayers}
        hasActiveFilters={hasActiveFilters}
        isFetching={isFetching}
        searchInputRef={searchInputRef}
        searchQuery={searchQuery}
        teams={teams}
        teamFilter={teamFilter}
        totalPlayers={result?.total_players}
        onAdd={() => setIsAddPlayerOpen(true)}
        onFilterChange={handleFilterChange}
        onSearchChange={setSearchQuery}
      />

      {successToast ? (
        <SuccessToast
          key={successToast.id}
          message={successToast.message}
          onDismiss={dismissSuccessToast}
        />
      ) : null}

      <PlayerDirectoryResults
        canManagePlayers={canManagePlayers}
        errorMessage={errorMessage}
        isFetching={isFetching}
        listRegionRef={listRegionRef}
        result={result}
        search={committedSearch}
        teamFilter={teamFilter}
        onAddPlayer={() => setIsAddPlayerOpen(true)}
        onClearSearch={handleClearSearch}
        onPageChange={handlePageChange}
        onRetry={handleRetry}
        onSelectPlayer={setSelectedPlayer}
      />

      <PlayersPageModals
        canManagePlayers={canManagePlayers}
        isAddPlayerOpen={isAddPlayerOpen}
        selectedPlayer={selectedPlayer}
        onAddPlayerClose={() => setIsAddPlayerOpen(false)}
        onPlayerMutation={handlePlayerMutation}
        onSelectPlayer={setSelectedPlayer}
      />
    </section>
  )
}
