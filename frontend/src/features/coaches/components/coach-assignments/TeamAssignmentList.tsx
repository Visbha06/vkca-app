import type { TeamResponse } from '@features/teams/types/team'

interface TeamAssignmentListProps {
  teams: TeamResponse[]
  selectedTeamIds: Set<string>
  disabled: boolean
  onToggle: (teamId: string) => void
}

export default function TeamAssignmentList({
  teams,
  selectedTeamIds,
  disabled,
  onToggle,
}: TeamAssignmentListProps) {
  if (teams.length === 0) {
    return (
      <p className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-700">
        No teams are available to assign yet.
      </p>
    )
  }

  return (
    <fieldset disabled={disabled}>
      <legend className="sr-only">Available teams</legend>
      <div className="space-y-2">
        {teams.map((team) => (
          <label
            key={team.id}
            className="flex min-h-14 cursor-pointer items-center gap-3 rounded-lg border border-slate-200 px-4 py-3 transition-colors hover:border-academy hover:bg-academy/10 has-[:checked]:border-academy has-[:checked]:bg-academy/10 has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-60"
          >
            <input
              type="checkbox"
              className="size-5 rounded border-slate-400 text-academy focus:ring-2 focus:ring-academy focus:ring-offset-2"
              checked={selectedTeamIds.has(team.id)}
              onChange={() => onToggle(team.id)}
            />
            <span className="min-w-0 flex-1">
              <span className="block font-semibold text-slate-900">
                {team.name}
              </span>
              <span className="mt-0.5 block text-sm text-slate-600">
                {team.age_group} · {team.player_count}{' '}
                {team.player_count === 1 ? 'player' : 'players'}
              </span>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
