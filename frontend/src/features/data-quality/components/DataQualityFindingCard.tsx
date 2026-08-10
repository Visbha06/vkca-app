import type { DataQualityFinding } from '../api/dataQualityApi'
import type { DataQualityWorkflowPath } from '../types/dataQuality'
import {
  getWorkflowTarget,
  requiresManualReview,
} from '../utils/dataQualityNavigation'

interface DataQualityFindingCardProps {
  finding: DataQualityFinding
  onNavigate?: (path: DataQualityWorkflowPath, label: string) => void
  onRemediate?: (finding: DataQualityFinding) => void
}

const severityClasses = {
  critical: 'border-rose-300 bg-rose-50 text-rose-950',
  warning: 'border-amber-300 bg-amber-50 text-amber-950',
  info: 'border-sky-300 bg-sky-50 text-sky-950',
}

const remediationLabels = {
  normalize_roster_order: 'Normalize roster order',
  remove_inactive_player: 'Remove inactive player',
  remove_inactive_assistant_assignment: 'Remove assignment',
}

export default function DataQualityFindingCard({
  finding,
  onNavigate,
  onRemediate,
}: DataQualityFindingCardProps) {
  const isManualReview = requiresManualReview(finding.rule_id)
  return (
    <article className="min-w-0 px-5 py-5 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="break-words text-sm font-semibold text-slate-900">{finding.entity_label}</p>
          <h2 className="mt-1 break-words text-lg font-bold text-slate-900">{finding.title}</h2>
        </div>
        <span className={`shrink-0 rounded-md border px-2 py-1 text-sm font-semibold capitalize ${severityClasses[finding.severity]}`}>
          {finding.severity}
        </span>
      </div>
      <p className="mt-3 max-w-3xl break-words text-sm leading-6 text-slate-700">{finding.explanation}</p>
      <p className="mt-3 break-words text-sm font-semibold leading-6 text-slate-800">{finding.recommended_action}</p>
      {finding.direct_remediation !== null ? (
        <button
          type="button"
          className="mt-4 min-h-11 w-full rounded-lg border border-academy bg-white px-4 text-sm font-semibold text-slate-800 transition-colors hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 sm:w-auto"
          onClick={() => onRemediate?.(finding)}
        >
          {remediationLabels[finding.direct_remediation.action]}
        </button>
      ) : isManualReview ? (
        <p className="mt-4 text-sm font-semibold text-slate-700">Manual review required</p>
      ) : (
        <button
          type="button"
          className="mt-4 min-h-11 w-full rounded-lg border border-academy bg-white px-4 text-sm font-semibold text-slate-800 transition-colors hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 sm:w-auto"
          onClick={() => onNavigate?.(getWorkflowTarget(finding.rule_id), finding.entity_label)}
        >
          Navigate to Fix
        </button>
      )}
    </article>
  )
}
