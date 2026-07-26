import { useState } from 'react'
import { fetchPlayer } from '../api/playerApi'
import { useAuth } from '../auth/AuthContext'
import TeamCardGrid from '../components/TeamCardGrid'
import TeamDetailsModal from '../components/TeamDetailsModal'
import TeamPageLoadingSkeleton from '../components/TeamPageLoadingSkeleton'
import Pagination from '../components/Pagination'
import PlayerDetailsModal from '../components/PlayerDetailsModal'
import useTeams from '../hooks/useTeams'
import type { PlayerResponse } from '../types/player'
import type { TeamResponse, TeamRosterPlayerResponse } from '../types/team'

export default function TeamsPage() {
  const { user } = useAuth()
  const canManageTeams = user?.role === 'head coach' || user?.role === 'assistant coach'
  const { errorMessage, isFetching, result, retry, setPage } = useTeams()
  const [selectedTeam, setSelectedTeam] = useState<TeamResponse | null>(null)
  const [selectedPlayer, setSelectedPlayer] = useState<PlayerResponse | null>(null)

  function handlePlayerInfo(player: TeamRosterPlayerResponse) {
    setSelectedTeam(null)
    void fetchPlayer(player.player_id).then(setSelectedPlayer).catch(() => undefined)
  }

  const initialError = errorMessage !== null && result === null

  return (
    <section className="mx-auto w-full max-w-7xl">
      <header className="mb-6 flex flex-col gap-4 border-b border-slate-200 pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-[-0.025em] text-slate-900" tabIndex={-1}>Teams</h1>
          <p className="mt-2 max-w-prose text-slate-600">Organize academy squads and review their active roster.</p>
        </div>
        {canManageTeams ? <button type="button" disabled title="Team creation will be available in the next phase." className="min-h-11 rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50">Create Team</button> : null}
      </header>

      {initialError ? (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-950 sm:p-6"><p className="font-semibold">{errorMessage}</p><button type="button" className="mt-4 min-h-11 rounded-lg border border-red-800 px-4 text-sm font-semibold hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2" onClick={retry}>Retry</button></div>
      ) : (
        <>
          {errorMessage !== null ? <div role="alert" className="mb-4 flex flex-col gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-red-950 sm:flex-row sm:items-center sm:justify-between"><p className="text-sm font-semibold">Unable to update the team results. Previous results are still shown.</p><button type="button" className="min-h-11 shrink-0 rounded-lg border border-red-800 px-4 text-sm font-semibold hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2" onClick={retry}>Retry</button></div> : null}
          {isFetching && result === null ? <TeamPageLoadingSkeleton /> : null}
          {result !== null && result.teams.length === 0 ? <div className="rounded-xl border border-slate-200 bg-white px-5 py-12 text-center sm:px-6"><p className="font-semibold text-slate-900">No teams are available.</p><p className="mx-auto mt-2 max-w-prose text-sm leading-6 text-slate-600">Team squads will appear here when they are available.</p></div> : null}
          {result !== null && result.teams.length > 0 ? <div aria-busy={isFetching}><TeamCardGrid teams={result.teams} onSelect={setSelectedTeam} /></div> : null}
          {result !== null && result.total_pages > 1 ? <div className="mt-8 border-t border-slate-200 pt-6"><Pagination page={result.page} totalPages={result.total_pages} isLoading={isFetching} onPageChange={setPage} /></div> : null}
        </>
      )}

      {selectedTeam !== null ? <TeamDetailsModal team={selectedTeam} canManageTeams={canManageTeams} onClose={() => setSelectedTeam(null)} onPlayerInfo={handlePlayerInfo} /> : null}
      {selectedPlayer !== null ? <PlayerDetailsModal player={selectedPlayer} onClose={() => setSelectedPlayer(null)} /> : null}
    </section>
  )
}
