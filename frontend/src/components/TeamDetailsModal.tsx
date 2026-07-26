import type {
  TeamResponse,
  TeamRosterPlayerResponse,
  TeamRosterResponse,
} from '../types/team'
import AgeGroupBadge from './AgeGroupBadge'
import ModalDialog from './ModalDialog'
import useTeamRoster from '../hooks/useTeamRoster'

interface TeamDetailsModalProps {
  team: TeamResponse
  canManageTeams: boolean
  onClose: () => void
  onEdit?: (roster: TeamRosterResponse) => void
  onPlayerInfo: (player: TeamRosterPlayerResponse) => void
}

export default function TeamDetailsModal({
  team,
  canManageTeams,
  onClose,
  onEdit,
  onPlayerInfo,
}: TeamDetailsModalProps) {
  const { errorMessage, isLoading, retry, roster } = useTeamRoster(team.id)

  return (
    <ModalDialog labelledBy="team-details-title" onClose={onClose} testId="team-details-backdrop">
      <div className="relative bg-white text-slate-900">
        <header className="border-b border-slate-200 px-5 py-4 pr-16 sm:px-6 sm:pr-16">
          <h2 id="team-details-title" className="text-xl font-bold leading-7 text-slate-900">
            {team.name}
          </h2>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <AgeGroupBadge ageGroup={team.age_group} />
            <p className="text-sm font-medium text-slate-700">
              {team.player_count} / 15 {team.player_count === 1 ? 'player' : 'players'}
            </p>
          </div>
        </header>

        <div className="px-5 py-5 sm:px-6">
          <h3 className="text-base font-bold text-slate-900">Roster</h3>
          {isLoading ? <p role="status" className="mt-3 text-sm text-slate-600">Loading roster</p> : null}
          {errorMessage !== null ? (
            <div role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-950">
              <p className="font-semibold">{errorMessage}</p>
              <button type="button" className="mt-3 min-h-11 rounded-lg border border-red-800 px-4 font-semibold hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2" onClick={retry}>Retry</button>
            </div>
          ) : null}
          {!isLoading && errorMessage === null && roster?.players.length === 0 ? (
            <p className="mt-3 text-sm leading-6 text-slate-600">No players are currently assigned to this team.</p>
          ) : null}
          {roster !== null && roster.players.length > 0 ? (
            <ol className="mt-3 divide-y divide-slate-200 border-y border-slate-200">
              {roster.players.map((player) => (
                <li key={player.player_id} className="flex min-h-14 items-center justify-between gap-3 py-2">
                  <div className={player.is_active ? '' : 'text-slate-500'}>
                    <p className="font-semibold text-slate-900">{player.first_name} {player.last_name}</p>
                    {!player.is_active ? <p className="text-sm">Inactive</p> : null}
                  </div>
                  <button type="button" className="min-h-11 rounded-lg border border-academy px-3 text-sm font-semibold text-slate-900 hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2" aria-label={`View ${player.first_name} ${player.last_name}`} onClick={() => onPlayerInfo(player)}>Info</button>
                </li>
              ))}
            </ol>
          ) : null}
          {canManageTeams && onEdit !== undefined ? (
            <div className="mt-5 flex justify-end border-t border-slate-200 pt-4">
              <button type="button" disabled={roster === null || isLoading} className="min-h-11 rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-400" onClick={() => {
                if (roster !== null) onEdit(roster)
              }}>Edit Team</button>
            </div>
          ) : null}
        </div>
        <button type="button" aria-label="Close team details" data-modal-initial-focus className="absolute right-3 top-3 flex size-11 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 sm:right-4 sm:top-4" onClick={onClose}>
          <svg aria-hidden="true" className="size-6" fill="none" viewBox="0 0 24 24"><path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeLinecap="round" strokeWidth="2" /></svg>
        </button>
      </div>
    </ModalDialog>
  )
}
