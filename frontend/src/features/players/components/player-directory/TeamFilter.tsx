import type { ChangeEvent } from 'react'
import type { TeamSummary } from '../../types/player'

export const UNASSIGNED_FILTER = '__unassigned__'

interface TeamFilterProps {
  teams: TeamSummary[]
  value: string | null
  onChange: (teamId: string | null) => void
  disabled?: boolean
}

export default function TeamFilter({
  teams,
  value,
  onChange,
  disabled = false,
}: TeamFilterProps) {
  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    onChange(event.target.value === '' ? null : event.target.value)
  }

  return (
    <div className="w-full sm:w-auto sm:min-w-64">
      <label
        htmlFor="player-team-filter"
        className="mb-2 block text-sm font-semibold text-slate-800"
      >
        Filter by team
      </label>
      <select
        id="player-team-filter"
        className="min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/40 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500"
        disabled={disabled}
        value={value ?? ''}
        onChange={handleChange}
      >
        <option value="">All Players</option>
        {teams.map((team) => (
          <option key={team.id} value={team.id}>
            {team.name}
          </option>
        ))}
        <option value={UNASSIGNED_FILTER}>Unassigned Players</option>
      </select>
    </div>
  )
}
