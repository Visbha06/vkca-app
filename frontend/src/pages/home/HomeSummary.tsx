import { DashboardSummary } from '@features/dashboard/components'
import type { DashboardSummary as DashboardSummaryData } from '@features/dashboard/types/dashboard'

interface HomeSummaryProps {
  summary: DashboardSummaryData
  onRetry: () => void
}

export default function HomeSummary({ summary, onRetry }: HomeSummaryProps) {
  return <DashboardSummary summary={summary} onRetry={onRetry} />
}
