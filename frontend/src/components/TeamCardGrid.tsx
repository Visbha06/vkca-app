import type { TeamResponse } from '../types/team'
import TeamCard from './TeamCard'

interface TeamCardGridProps {
  teams: TeamResponse[]
  onSelect: (team: TeamResponse) => void
}

export default function TeamCardGrid({ teams, onSelect }: TeamCardGridProps) {
  return (
    <ul aria-label="Teams" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {teams.map((team) => (
        <li key={team.id} className="h-full">
          <TeamCard team={team} onSelect={onSelect} />
        </li>
      ))}
    </ul>
  )
}
