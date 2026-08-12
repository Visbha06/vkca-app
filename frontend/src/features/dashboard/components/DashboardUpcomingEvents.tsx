import { Link } from 'react-router'
import type { DashboardUpcomingEventsSection } from '../types/dashboard'
import {
  dashboardAudience,
  formatDashboardDate,
  formatDashboardTime,
  titleCase,
} from './dashboardFormatting'

interface DashboardUpcomingEventsProps {
  section: DashboardUpcomingEventsSection
  onRetry: () => void
}

export default function DashboardUpcomingEvents({
  section,
  onRetry,
}: DashboardUpcomingEventsProps) {
  return (
    <section
      id="upcoming-events"
      aria-labelledby="upcoming-events-heading"
      className="min-w-0 scroll-mt-6 lg:col-span-2"
      tabIndex={-1}
    >
      <div className="flex items-center justify-between gap-4">
        <h2
          id="upcoming-events-heading"
          className="text-xl font-bold text-slate-900"
        >
          Upcoming events
        </h2>
        <Link
          to="/calendar"
          className="inline-flex min-h-11 items-center rounded-md px-2 text-sm font-semibold text-slate-700 underline decoration-academy decoration-2 underline-offset-4 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
        >
          View calendar
        </Link>
      </div>

      {section.status === 'ready' && section.data.length > 0 ? (
        <ul className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white">
          {section.data.map((event) => (
            <li
              key={event.occurrence_id}
              className="grid gap-4 border-b border-slate-200 p-5 last:border-b-0 sm:grid-cols-6 sm:items-center"
            >
              <time
                dateTime={event.event_date}
                className="font-semibold tabular-nums text-slate-700 sm:col-span-1 sm:text-center"
              >
                {formatDashboardDate(event.event_date)}
              </time>
              <div className="min-w-0 sm:col-span-4">
                <p className="text-sm font-medium text-slate-600">
                  {formatDashboardTime(event)}
                </p>
                <h3 className="mt-1 break-words font-bold text-slate-900">
                  {event.name}
                </h3>
                <p className="mt-1 text-sm text-slate-600">
                  {dashboardAudience(event)}
                </p>
              </div>
              <span className="w-fit rounded-md border border-academy px-2.5 py-1 text-xs font-semibold text-slate-800 sm:col-span-1 sm:justify-self-end">
                {titleCase(event.event_type)}
              </span>
            </li>
          ))}
        </ul>
      ) : section.status === 'unavailable' ? (
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
              Retry upcoming events
            </button>
          ) : null}
        </div>
      ) : (
        <p className="mt-4 rounded-xl border border-slate-200 bg-white p-5 text-sm leading-6 text-slate-700">
          {section.status === 'ready'
            ? 'No upcoming events in your scope.'
            : section.message}
        </p>
      )}
    </section>
  )
}
