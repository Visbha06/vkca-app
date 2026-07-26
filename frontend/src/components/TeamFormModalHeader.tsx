import type { TeamResponse } from '../types/team'

interface TeamFormModalHeaderProps {
  team?: TeamResponse
}

export default function TeamFormModalHeader({
  team,
}: TeamFormModalHeaderProps) {
  return (
    <header className="border-b border-slate-200 p-5 pr-16 sm:p-6 sm:pr-16">
      <h2 id="team-form-title" className="text-xl font-bold">
        {team === undefined ? 'Create Team' : `Edit ${team.name}`}
      </h2>
      <p className="mt-2 max-w-prose text-sm leading-6 text-slate-700">
        {team === undefined
          ? 'Add team details and select 7–15 active players.'
          : 'Update team details and replace the complete ordered roster.'}
      </p>
    </header>
  )
}
