import { Link } from 'react-router'
import { useAuth } from '@features/auth'
import { useRecentBusinessAudit } from '@features/audit/hooks/useBusinessAudit'
import { formatBusinessAuditRelativeTime } from '@features/audit/utils/businessAuditTime'
import type { BusinessAuditEvent } from '@features/audit/types/businessAudit'
import {
  CalendarIcon,
  CoachesIcon,
  PlayersIcon,
  TeamsIcon,
} from '@shared/components/icons/NavIcons'

const upcomingEvents = [
  ['21', 'Tue', '5:00 PM – 6:30 PM', 'Batting fundamentals – U15', 'Indoor Net 1 · 16 players', 'Training'],
  ['23', 'Thu', '4:30 PM – 6:00 PM', 'Bowling technique – U17', 'Outdoor Nets · 14 players', 'Training'],
  ['25', 'Sat', '10:30 AM – 1:30 PM', 'VKCA U14 vs Northside CC', 'Riverside Oval · 18 selected', 'Match'],
] as const

const categoryIcons = {
  calendar: CalendarIcon,
  coach: CoachesIcon,
  player: PlayersIcon,
  roster: TeamsIcon,
  team: TeamsIcon,
} as const

function categoryLabel(category: BusinessAuditEvent['action_category']) {
  return `${category.slice(0, 1).toUpperCase()}${category.slice(1)}`
}

function isDashboardEvent(event: BusinessAuditEvent) {
  const category = String(event.action_category)
  const action = String(event.action_type)
  return !['match', 'performance', 'player-statistics'].some(
    (excluded) => category === excluded || action.startsWith(`${excluded}.`),
  )
}

function UpcomingEvents() {
  return (
    <section aria-labelledby="upcoming-events-heading" className="min-w-0 lg:col-span-2">
      <div className="flex items-center justify-between gap-4">
        <h2 id="upcoming-events-heading" className="text-xl font-bold text-slate-900">Upcoming events</h2>
        <Link to="/calendar" className="rounded-md px-2 py-1 text-sm font-semibold text-slate-700 underline decoration-academy decoration-2 underline-offset-4 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2">View calendar</Link>
      </div>
      <ul className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white">
        {upcomingEvents.map(([day, weekday, time, title, detail, category]) => (
          <li key={`${day}-${title}`} className="grid gap-4 border-b border-slate-200 p-5 last:border-b-0 sm:grid-cols-6 sm:items-center">
            <time className="flex items-baseline gap-2 sm:col-span-1 sm:block sm:text-center" dateTime={`2026-07-${day}`}>
              <span className="text-xs font-bold text-slate-600 sm:block">Jul</span>
              <span className="text-2xl font-bold tabular-nums text-slate-900 sm:block">{day}</span>
              <span className="text-xs font-semibold text-slate-600 sm:block">{weekday}</span>
            </time>
            <div className="min-w-0 sm:col-span-4">
              <p className="text-sm font-medium text-slate-600">{time}</p>
              <h3 className="mt-1 font-bold text-slate-900">{title}</h3>
              <p className="mt-1 text-sm text-slate-600">{detail}</p>
            </div>
            <span className="w-fit rounded-md border border-academy px-2.5 py-1 text-xs font-semibold text-slate-800 sm:col-span-1 sm:justify-self-end">{category}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function RecentActivity() {
  const { user } = useAuth()
  const { errorMessage, isLoading, result, retry } = useRecentBusinessAudit()

  if (user?.role !== 'head coach') return null

  const events = (result?.events ?? []).filter(isDashboardEvent).slice(0, 4)

  return (
    <section aria-labelledby="recent-activity-heading" className="min-w-0 lg:col-span-1 lg:border-l lg:border-slate-200 lg:pl-8">
      <div className="flex items-start justify-between gap-3">
        <h2 id="recent-activity-heading" className="text-xl font-bold text-slate-900">Recent academy activity</h2>
        <Link to="/audit-log" className="shrink-0 rounded-md px-2 py-1 text-sm font-semibold text-slate-700 underline decoration-academy decoration-2 underline-offset-4 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2">View all activity</Link>
      </div>
      {isLoading ? (
        <p role="status" className="mt-5 rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-600">Loading recent academy activity…</p>
      ) : errorMessage ? (
        <div role="alert" className="mt-5 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-950">
          <p>Unable to load recent academy activity.</p>
          <button type="button" onClick={retry} className="mt-3 min-h-11 rounded-md border border-red-800 px-3 font-semibold hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2">Retry</button>
        </div>
      ) : events.length === 0 ? (
        <p className="mt-5 rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-600">No recent academy activity yet.</p>
      ) : (
        <ol className="ml-5 mt-5 space-y-6 border-l border-slate-200 pl-5">
          {events.map((event) => {
            const Icon = categoryIcons[event.action_category]
            const actor = event.actor_display_name ?? 'System activity'
            const detail = event.target_label === null ? actor : `${actor} · ${event.target_label}`
            return (
              <li key={event.id} className="relative flex min-w-0 gap-3">
                <span className="absolute -left-10 flex size-9 items-center justify-center rounded-full bg-academy text-slate-900 ring-4 ring-slate-50" aria-hidden="true"><Icon className="size-5" /></span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold text-slate-900">{event.summary}</h3>
                      <span className="rounded-md border border-academy bg-white px-2 py-1 text-xs font-semibold text-slate-800">{categoryLabel(event.action_category)}</span>
                    </div>
                    <time dateTime={event.created_at} className="text-xs font-medium text-slate-500">{formatBusinessAuditRelativeTime(event.created_at)}</time>
                  </div>
                  <p className="mt-1 text-sm leading-6 text-slate-600">{detail}</p>
                </div>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}

export default function HomeSchedule() {
  return <div className="grid gap-8 lg:grid-cols-3"><UpcomingEvents /><RecentActivity /></div>
}
