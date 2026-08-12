import { Link } from 'react-router'
import type { DashboardContext } from '../types/dashboard'
import { formatDashboardDate } from './dashboardFormatting'

interface MyTeamsPanelProps {
  context: Extract<DashboardContext, { kind: 'my_teams' }>
}

export default function MyTeamsPanel({ context }: MyTeamsPanelProps) {
  return (
    <section
      aria-labelledby="my-teams-heading"
      className="min-w-0 lg:col-span-1 lg:border-l lg:border-slate-200 lg:pl-8"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="my-teams-heading" className="text-xl font-bold text-slate-900">
          My teams
        </h2>
        <Link
          to={context.view_all_path}
          className="inline-flex min-h-11 items-center rounded-md px-2 text-sm font-semibold text-slate-700 underline decoration-academy decoration-2 underline-offset-4 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
        >
          View teams
        </Link>
      </div>
      {context.teams.length === 0 ? (
        <p className="mt-4 rounded-xl border border-slate-200 bg-white p-5 text-sm leading-6 text-slate-700">
          No teams are currently in your scope.
        </p>
      ) : (
        <ul className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white">
          {context.teams.map((team) => (
            <li key={team.id} className="min-w-0 border-b border-slate-200 p-5 last:border-b-0">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h3 className="break-words font-semibold text-slate-900">{team.name}</h3>
                <span className="rounded-md border border-academy px-2 py-1 text-xs font-semibold text-slate-800">{team.age_group}</span>
              </div>
              <dl className="mt-3 grid gap-x-3 gap-y-1 text-sm leading-6 text-slate-600 sm:grid-cols-[auto_minmax(0,1fr)]">
                <dt className="font-medium text-slate-700">Roster</dt>
                <dd>{team.active_player_count} active players</dd>
                {team.next_event !== null ? <>
                  <dt className="font-medium text-slate-700">Next</dt>
                  <dd className="min-w-0 break-words">{team.next_event.name} · {formatDashboardDate(team.next_event.event_date)}</dd>
                </> : null}
                {(team.coaches ?? []).length > 0 ? <>
                  <dt className="font-medium text-slate-700">Coaches</dt>
                  <dd className="min-w-0 break-words">{(team.coaches ?? []).map((coach) => coach.display_name).join(', ')}</dd>
                </> : null}
              </dl>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
