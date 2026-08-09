import type { DataQualityFinding } from '../api/dataQualityApi'
import type { DataQualityWorkflowPath } from '../types/dataQuality'
import DataQualityFindingCard from './DataQualityFindingCard'

interface DataQualityFindingListProps {
  findings: DataQualityFinding[]
  onNavigate: (path: DataQualityWorkflowPath, label: string) => void
  onRemediate: (finding: DataQualityFinding) => void
}

export default function DataQualityFindingList({
  findings,
  onNavigate,
  onRemediate,
}: DataQualityFindingListProps) {
  return (
    <section aria-label="Current findings" className="divide-y divide-slate-200 overflow-hidden rounded-xl border border-slate-200 bg-white">
      {findings.map((finding) => (
        <DataQualityFindingCard
          key={finding.finding_id}
          finding={finding}
          onNavigate={onNavigate}
          onRemediate={onRemediate}
        />
      ))}
    </section>
  )
}
