import { Link } from 'react-router'
import type { DashboardContext } from '../types/dashboard'

interface RecentAcademyActivityProps {
  context: Extract<DashboardContext, { kind: 'recent_activity' }>
}

export default function RecentAcademyActivity({
  context,
}: RecentAcademyActivityProps) {
  return (
    <section
      aria-labelledby="recent-activity-heading"
      className="min-w-0 lg:col-span-1 lg:border-l lg:border-slate-200 lg:pl-8"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="recent-activity-heading" className="text-xl font-bold text-slate-900">
          Recent academy activity
        </h2>
        <Link
          to={context.view_all_path}
          className="inline-flex min-h-11 items-center rounded-md px-2 text-sm font-semibold text-slate-700 underline decoration-academy decoration-2 underline-offset-4 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
        >
          View all activity
        </Link>
      </div>
      {context.events.length === 0 ? (
        <p className="mt-4 rounded-xl border border-slate-200 bg-white p-5 text-sm leading-6 text-slate-700">
          No recent academy activity yet.
        </p>
      ) : (
        <ol className="mt-4 border-l border-slate-200 pl-4">
          {context.events.map((event) => (
            <li key={event.id} className="relative border-b border-slate-200 py-4 first:pt-0 last:border-b-0 last:pb-0">
              <span aria-hidden="true" className="absolute -left-[21px] top-5 size-2 rounded-full bg-academy first:top-1" />
              <h3 className="break-words font-semibold text-slate-900">{event.summary}</h3>
              <p className="mt-1 break-words text-sm leading-6 text-slate-600">
                {event.actor_display_name ?? 'System activity'}
                {event.target_label === null ? '' : ` · ${event.target_label}`}
              </p>
              <time dateTime={event.created_at} className="mt-2 block text-xs font-medium text-slate-500">
                {new Intl.DateTimeFormat('en-US', { day: 'numeric', month: 'short' }).format(new Date(event.created_at))}
              </time>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
