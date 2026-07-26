import type { TeamResponse } from '../../types/team'
import TeamRow from './TeamRow'

interface TeamCollectionProps {
  teams: TeamResponse[]
  onSelect: (team: TeamResponse) => void
}

export default function TeamCollection({
  teams,
  onSelect,
}: TeamCollectionProps) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <div
        aria-hidden="true"
        className="hidden grid-cols-[2.75rem_minmax(0,1.5fr)_minmax(7rem,1fr)_minmax(7rem,0.9fr)_minmax(6.5rem,0.8fr)_1.25rem] gap-x-4 border-b border-slate-200 bg-slate-50 px-5 py-3 text-sm font-semibold text-slate-700 lg:grid"
      >
        <span />
        <span>Team</span>
        <span>Roster</span>
        <span>Availability</span>
        <span>Updated</span>
        <span />
      </div>
      <ul aria-label="Teams" className="divide-y divide-slate-200">
        {teams.map((team) => (
          <li key={team.id}>
            <TeamRow team={team} onSelect={onSelect} />
          </li>
        ))}
      </ul>
    </div>
  )
}
