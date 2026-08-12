import { Link } from 'react-router'
import { useAuth } from '@features/auth'
import {
  DashboardErrorState,
  DashboardLoadingState,
} from '@features/dashboard/components'
import { useDashboard } from '@features/dashboard/hooks/useDashboard'
import type { DashboardResponse } from '@features/dashboard/types/dashboard'
import { CalendarIcon, TeamsIcon } from '@shared/components/icons/NavIcons'
import HomeSchedule from './HomeSchedule'
import HomeSummary from './HomeSummary'

function PrimaryAction({
  dashboard,
  role,
}: {
  dashboard: DashboardResponse | null
  role: 'head coach' | 'assistant coach' | 'player'
}) {
  if (role === 'head coach' || role === 'assistant coach') {
    return (
      <Link
        to="/calendar"
        className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
      >
        <CalendarIcon className="size-5" />
        Schedule event
      </Link>
    )
  }

  const hasScopedTeams =
    dashboard?.context.status === 'ready' &&
    dashboard.context.data.kind === 'my_teams' &&
    dashboard.context.data.teams.length > 0
  const eventsAreEmpty =
    dashboard?.upcoming_events.status === 'empty' ||
    (dashboard?.upcoming_events.status === 'ready' &&
      dashboard.upcoming_events.data.length === 0)
  if (eventsAreEmpty && hasScopedTeams) {
    return (
      <Link
        to="/teams"
        className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
      >
        <TeamsIcon className="size-5" />
        View Teams
      </Link>
    )
  }

  return (
    <a
      href="#upcoming-events"
      onClick={() => document.getElementById('upcoming-events')?.focus()}
      className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
    >
      <CalendarIcon className="size-5" />
      View Upcoming Events
    </a>
  )
}

export default function HomePage() {
  const { user } = useAuth()
  const dashboard = useDashboard()
  const role = user?.role ?? dashboard.result?.user.role ?? 'player'
  const firstName = user?.first_name.trim() || 'there'
  const greeting =
    role === 'player'
      ? `Welcome back, ${firstName}`
      : `Welcome back, Coach ${firstName}`

  return (
    <div className="mx-auto w-full min-w-0 max-w-7xl">
      <header className="flex flex-col gap-6 border-b border-slate-200 pb-8 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <h1
            className="break-words text-3xl font-bold tracking-tight text-slate-900 md:text-4xl"
            tabIndex={-1}
          >
            {greeting}
          </h1>
          <p className="mt-2 max-w-2xl text-base leading-7 text-slate-600 md:text-lg">
            Here’s what’s happening at the academy.
          </p>
        </div>
        <nav aria-label="Primary action" className="flex shrink-0">
          <PrimaryAction dashboard={dashboard.result} role={role} />
        </nav>
      </header>

      {dashboard.isInitialLoading ? <DashboardLoadingState /> : null}
      {dashboard.result === null && dashboard.errorMessage !== null ? (
        <DashboardErrorState
          message={dashboard.errorMessage}
          onRetry={dashboard.retry}
        />
      ) : null}
      {dashboard.result !== null ? (
        <>
          {dashboard.errorMessage !== null ? (
            <div
              role="alert"
              className="mt-6 flex flex-col gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950 sm:flex-row sm:items-center sm:justify-between"
            >
              <p>Unable to refresh your dashboard. Previous live values remain visible.</p>
              <button
                type="button"
                onClick={dashboard.retry}
                className="min-h-11 shrink-0 rounded-lg border border-amber-900 bg-white px-4 font-semibold hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-900 focus:ring-offset-2"
              >
                Retry dashboard refresh
              </button>
            </div>
          ) : null}
          {dashboard.isFetching ? (
            <p role="status" className="sr-only">
              Refreshing dashboard
            </p>
          ) : null}
          <HomeSummary
            summary={dashboard.result.summary}
            onRetry={dashboard.retry}
          />
          <HomeSchedule
            upcomingEvents={dashboard.result.upcoming_events}
            context={dashboard.result.context}
            onRetry={dashboard.retry}
            role={dashboard.result.user.role}
          />
        </>
      ) : null}
    </div>
  )
}
