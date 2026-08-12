import { Link } from 'react-router'
import { DashboardUpcomingEvents } from '@features/dashboard/components'
import type {
  DashboardContextSection,
  DashboardUpcomingEventsSection,
} from '@features/dashboard/types/dashboard'
import { formatDashboardDate } from '@features/dashboard/components/dashboardFormatting'

interface HomeScheduleProps {
  upcomingEvents: DashboardUpcomingEventsSection
  context: DashboardContextSection
  onRetry: () => void
  role: 'head coach' | 'assistant coach' | 'player'
}

function ContextMessage({
  section,
  onRetry,
  role,
}: {
  section: Exclude<DashboardContextSection, { status: 'ready' }>
  onRetry: () => void
  role: HomeScheduleProps['role']
}) {
  return (
    <section
      aria-labelledby="dashboard-context-heading"
      className="min-w-0 lg:col-span-1 lg:border-l lg:border-slate-200 lg:pl-8"
    >
      <h2
        id="dashboard-context-heading"
        className="text-xl font-bold text-slate-900"
      >
        {role === 'head coach' ? 'Recent academy activity' : 'My teams'}
      </h2>
      {section.status === 'unavailable' ? (
        <div
          role="alert"
          className="mt-4 rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-950"
        >
          <p>{section.message}</p>
          {section.retryable ? (
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 min-h-11 rounded-lg border border-red-800 bg-white px-4 font-semibold hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2"
            >
              Retry dashboard context
            </button>
          ) : null}
        </div>
      ) : (
        <p className="mt-4 rounded-xl border border-slate-200 bg-white p-5 text-sm leading-6 text-slate-700">
          {section.message}
        </p>
      )}
    </section>
  )
}

function RecentActivity({
  context,
}: {
  context: Extract<
    DashboardContextSection,
    { status: 'ready' }
  >['data'] & { kind: 'recent_activity' }
}) {
  return (
    <section
      aria-labelledby="recent-activity-heading"
      className="min-w-0 lg:col-span-1 lg:border-l lg:border-slate-200 lg:pl-8"
    >
      <div className="flex items-start justify-between gap-3">
        <h2
          id="recent-activity-heading"
          className="text-xl font-bold text-slate-900"
        >
          Recent academy activity
        </h2>
        <Link
          to={context.view_all_path}
          className="shrink-0 rounded-md px-2 py-1 text-sm font-semibold text-slate-700 underline decoration-academy decoration-2 underline-offset-4 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
        >
          View all activity
        </Link>
      </div>
      {context.events.length === 0 ? (
        <p className="mt-4 rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-700">
          No recent academy activity yet.
        </p>
      ) : (
        <ol className="mt-4 space-y-3">
          {context.events.map((event) => (
            <li
              key={event.id}
              className="rounded-xl border border-slate-200 bg-white p-4"
            >
              <h3 className="break-words font-semibold text-slate-900">
                {event.summary}
              </h3>
              <p className="mt-1 text-sm leading-6 text-slate-600">
                {event.actor_display_name ?? 'System activity'}
                {event.target_label === null ? '' : ` · ${event.target_label}`}
              </p>
              <time
                dateTime={event.created_at}
                className="mt-2 block text-xs font-medium text-slate-500"
              >
                {new Intl.DateTimeFormat('en-US', {
                  day: 'numeric',
                  month: 'short',
                }).format(new Date(event.created_at))}
              </time>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

function MyTeams({
  context,
}: {
  context: Extract<
    DashboardContextSection,
    { status: 'ready' }
  >['data'] & { kind: 'my_teams' }
}) {
  return (
    <section
      aria-labelledby="my-teams-heading"
      className="min-w-0 lg:col-span-1 lg:border-l lg:border-slate-200 lg:pl-8"
    >
      <div className="flex items-start justify-between gap-3">
        <h2 id="my-teams-heading" className="text-xl font-bold text-slate-900">
          My teams
        </h2>
        <Link
          to={context.view_all_path}
          className="shrink-0 rounded-md px-2 py-1 text-sm font-semibold text-slate-700 underline decoration-academy decoration-2 underline-offset-4 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
        >
          View teams
        </Link>
      </div>
      {context.teams.length === 0 ? (
        <p className="mt-4 rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-700">
          No teams are currently in your scope.
        </p>
      ) : (
        <ul className="mt-4 space-y-3">
          {context.teams.map((team) => (
            <li
              key={team.id}
              className="rounded-xl border border-slate-200 bg-white p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h3 className="break-words font-semibold text-slate-900">
                  {team.name}
                </h3>
                <span className="rounded-md border border-academy px-2 py-1 text-xs font-semibold text-slate-800">
                  {team.age_group}
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-600">
                {team.active_player_count} active{' '}
                {team.active_player_count === 1 ? 'player' : 'players'}
              </p>
              {team.next_event !== null ? (
                <p className="mt-1 text-sm text-slate-600">
                  Next: {team.next_event.name} ·{' '}
                  {formatDashboardDate(team.next_event.event_date)}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function DashboardContext({
  section,
  onRetry,
  role,
}: {
  section: DashboardContextSection
  onRetry: () => void
  role: HomeScheduleProps['role']
}) {
  if (section.status !== 'ready') {
    return <ContextMessage section={section} onRetry={onRetry} role={role} />
  }
  return section.data.kind === 'recent_activity' ? (
    <RecentActivity context={section.data} />
  ) : (
    <MyTeams context={section.data} />
  )
}

export default function HomeSchedule({
  upcomingEvents,
  context,
  onRetry,
  role,
}: HomeScheduleProps) {
  return (
    <div className="grid min-w-0 gap-8 lg:grid-cols-3">
      <DashboardUpcomingEvents section={upcomingEvents} onRetry={onRetry} />
      <DashboardContext section={context} onRetry={onRetry} role={role} />
    </div>
  )
}
