import { useState } from 'react'
import { useAuth } from '@features/auth'
import {
  fetchPlayer,
  PlayerDetailsModal,
  type PlayerResponse,
} from '@features/players'
import EmptyState from '@shared/components/feedback/EmptyState'
import SuccessMessage from '@shared/components/feedback/SuccessMessage'
import TeamCollection from '../components/team-directory/TeamCollection'
import TeamDirectoryHeader from '../components/team-directory/TeamDirectoryHeader'
import TeamDetailsModal from '../components/team-details/TeamDetailsModal'
import TeamFormModal from '../components/team-form/TeamFormModal'
import TeamPageLoadingSkeleton from '../components/team-directory/TeamPageLoadingSkeleton'
import Pagination from '@shared/components/navigation/Pagination'
import useTeamDirectory from '../hooks/useTeamDirectory'
import type {
  TeamResponse,
  TeamRosterResponse,
  TeamRosterSelection,
} from '../types/team'

export default function TeamsPage() {
  const { user } = useAuth()
  const canManageTeams = user?.role === 'head coach' || user?.role === 'assistant coach'
  const {
    ageGroupFilter,
    ageGroups,
    clearFilters,
    errorMessage,
    filteredTeams,
    isFetching,
    result,
    retry,
    searchInputRef,
    searchQuery,
    setAgeGroupFilter,
    setPage,
    setSearchQuery,
  } = useTeamDirectory()
  const [selectedTeam, setSelectedTeam] = useState<TeamResponse | null>(null)
  const [selectedPlayer, setSelectedPlayer] = useState<PlayerResponse | null>(null)
  const [isCreateTeamOpen, setIsCreateTeamOpen] = useState(false)
  const [editingTeam, setEditingTeam] = useState<{
    team: TeamResponse
    roster: TeamRosterResponse
  } | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  function handlePlayerInfo(player: TeamRosterSelection) {
    setSelectedTeam(null)
    void fetchPlayer(player.player_id).then(setSelectedPlayer).catch(() => undefined)
  }

  function handleEditTeam(roster: TeamRosterResponse) {
    if (selectedTeam === null) return
    setEditingTeam({ team: selectedTeam, roster })
    setSelectedTeam(null)
  }

  function handleFormPlayerInfo(player: TeamRosterSelection) {
    setIsCreateTeamOpen(false)
    setEditingTeam(null)
    handlePlayerInfo(player)
  }

  function handleTeamSaved(team: TeamResponse, action: 'created' | 'updated') {
    setSuccessMessage(`${team.name} was ${action} successfully.`)
    setIsCreateTeamOpen(false)
    setEditingTeam(null)
    retry()
  }

  const initialError = errorMessage !== null && result === null
  return (
    <section className="mx-auto w-full max-w-7xl">
      <TeamDirectoryHeader
        ageGroups={ageGroups}
        ageGroupFilter={ageGroupFilter}
        canManageTeams={canManageTeams}
        isFetching={isFetching}
        resultCount={result === null ? undefined : filteredTeams.length}
        searchInputRef={searchInputRef}
        searchQuery={searchQuery}
        totalTeams={result?.total_teams}
        onAgeGroupChange={setAgeGroupFilter}
        onCreate={() => setIsCreateTeamOpen(true)}
        onSearchChange={setSearchQuery}
      />

      {successMessage !== null ? (
        <SuccessMessage>{successMessage}</SuccessMessage>
      ) : null}

      {initialError ? (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-950 sm:p-6"><p className="font-semibold">{errorMessage}</p><button type="button" className="mt-4 min-h-11 rounded-lg border border-red-800 px-4 text-sm font-semibold hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2" onClick={retry}>Retry</button></div>
      ) : (
        <>
          {errorMessage !== null ? <div role="alert" className="mb-4 flex flex-col gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-red-950 sm:flex-row sm:items-center sm:justify-between"><p className="text-sm font-semibold">Unable to update the team results. Previous results are still shown.</p><button type="button" className="min-h-11 shrink-0 rounded-lg border border-red-800 px-4 text-sm font-semibold hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2" onClick={retry}>Retry</button></div> : null}
          {isFetching && result === null ? <TeamPageLoadingSkeleton /> : null}
          {result !== null && result.teams.length === 0 ? (
            <EmptyState
              title={
                canManageTeams
                  ? 'Create the first academy team'
                  : 'No academy teams are available yet'
              }
              description={
                canManageTeams
                  ? 'Set up the first squad to organize its age group and active roster.'
                  : 'Teams will appear here after a coach creates the first academy squad.'
              }
              action={
                canManageTeams
                  ? {
                      label: 'Create Team',
                      onClick: () => setIsCreateTeamOpen(true),
                    }
                  : undefined
              }
            />
          ) : null}
          {result !== null && result.teams.length > 0 && filteredTeams.length === 0 ? (
            <EmptyState
              title="No teams match these filters"
              description="Clear the search or choose another age group to view more teams."
              action={{
                label: 'Clear filters',
                onClick: clearFilters,
                variant: 'secondary',
              }}
            />
          ) : null}
          {filteredTeams.length > 0 ? (
            <div aria-busy={isFetching}>
              <TeamCollection teams={filteredTeams} onSelect={setSelectedTeam} />
            </div>
          ) : null}
          {result !== null && result.total_pages > 1 ? (
            <div className="mt-8 border-t border-slate-200 pt-6">
              <Pagination
                ariaLabel="Team pages"
                page={result.page}
                totalPages={result.total_pages}
                isLoading={isFetching}
                onPageChange={setPage}
              />
            </div>
          ) : null}
        </>
      )}

      {selectedTeam !== null ? <TeamDetailsModal team={selectedTeam} canManageTeams={canManageTeams} onClose={() => setSelectedTeam(null)} onEdit={canManageTeams ? handleEditTeam : undefined} onPlayerInfo={handlePlayerInfo} /> : null}
      {isCreateTeamOpen ? <TeamFormModal onClose={() => setIsCreateTeamOpen(false)} onSaved={(team) => handleTeamSaved(team, 'created')} onPlayerInfo={handleFormPlayerInfo} /> : null}
      {editingTeam !== null ? <TeamFormModal team={editingTeam.team} roster={editingTeam.roster} onClose={() => setEditingTeam(null)} onSaved={(team) => handleTeamSaved(team, 'updated')} onPlayerInfo={handleFormPlayerInfo} /> : null}
      {selectedPlayer !== null ? <PlayerDetailsModal player={selectedPlayer} onClose={() => setSelectedPlayer(null)} /> : null}
    </section>
  )
}
