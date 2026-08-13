import type { DashboardContextSection } from '../types/dashboard'
import MyTeamsPanel from './MyTeamsPanel'
import RecentAcademyActivity from './RecentAcademyActivity'

interface DashboardContextPanelProps {
  section: DashboardContextSection
  onRetry: () => void
  role: 'head coach' | 'assistant coach' | 'player'
}

function headingFor(role: DashboardContextPanelProps['role']) {
  return role === 'head coach' ? 'Recent academy activity' : 'My teams'
}

export default function DashboardContextPanel({
  section,
  onRetry,
  role,
}: DashboardContextPanelProps) {
  if (section.status === 'ready') {
    return section.data.kind === 'recent_activity' ? (
      <RecentAcademyActivity context={section.data} />
    ) : (
      <MyTeamsPanel context={section.data} />
    )
  }

  const heading = headingFor(role)
  return (
    <section
      aria-labelledby="dashboard-context-heading"
      className="min-w-0 lg:col-span-1 lg:border-l lg:border-slate-200 lg:pl-8"
    >
      <h2 id="dashboard-context-heading" className="text-xl font-bold text-slate-900">
        {heading}
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
              className="mt-3 min-h-11 rounded-lg border border-red-800 bg-white px-4 font-semibold hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2 motion-reduce:transition-none"
            >
              Retry dashboard context
            </button>
          ) : null}
        </div>
      ) : (
        <p
          role="status"
          aria-live="polite"
          className="mt-4 rounded-xl border border-slate-200 bg-white p-5 text-sm leading-6 text-slate-700"
        >
          {section.message}
        </p>
      )}
    </section>
  )
}
