import type { TeamResponse } from '@features/teams/types/team'

interface CoachTeamSelectorProps {
  teams: TeamResponse[]
  selectedTeamIds: string[]
  errorMessage: string | null
  isLoading: boolean
  isDisabled: boolean
  onToggle: (teamId: string) => void
}

export default function CoachTeamSelector({
  teams,
  selectedTeamIds,
  errorMessage,
  isLoading,
  isDisabled,
  onToggle,
}: CoachTeamSelectorProps) {
  return (
    <fieldset disabled={isDisabled}>
      <legend className="text-sm font-semibold text-slate-800">
        Initial team assignments <span className="font-normal">(optional)</span>
      </legend>
      <p className="mt-1 text-sm leading-6 text-slate-600">
        The account will always be created as an Assistant Coach.
      </p>
      {isLoading ? (
        <p role="status" className="mt-3 text-sm text-slate-700">
          Loading teams…
        </p>
      ) : errorMessage !== null ? (
        <p role="alert" className="mt-3 text-sm font-medium text-red-800">
          {errorMessage}
        </p>
      ) : teams.length === 0 ? (
        <p className="mt-3 text-sm text-slate-600">
          No teams are available yet.
        </p>
      ) : (
        <div className="mt-3 divide-y divide-slate-200 rounded-lg border border-slate-200">
          {teams.map((team) => (
            <label
              key={team.id}
              className="flex min-h-11 items-center gap-3 px-3 py-2 text-sm font-medium text-slate-800 hover:bg-academy/5"
            >
              <input
                type="checkbox"
                checked={selectedTeamIds.includes(team.id)}
                className="size-5 rounded border-slate-300 text-slate-900 focus:ring-academy"
                onChange={() => onToggle(team.id)}
              />
              <span>{team.name}</span>
              <span className="ml-auto text-slate-600">{team.age_group}</span>
            </label>
          ))}
        </div>
      )}
    </fieldset>
  )
}
