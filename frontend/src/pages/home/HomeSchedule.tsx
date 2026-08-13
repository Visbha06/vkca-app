import {
  DashboardContextPanel,
  DashboardUpcomingEvents,
} from '@features/dashboard/components'
import type {
  DashboardContextSection,
  DashboardUpcomingEventsSection,
} from '@features/dashboard/types/dashboard'

interface HomeScheduleProps {
  upcomingEvents: DashboardUpcomingEventsSection
  context: DashboardContextSection
  onRetry: () => void
  role: 'head coach' | 'assistant coach' | 'player'
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
      <DashboardContextPanel section={context} onRetry={onRetry} role={role} />
    </div>
  )
}
