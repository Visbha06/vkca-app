import type { AgeGroup } from '../types/team'
import { AGE_GROUP_LABELS } from '../utils/teamLabels'

interface AgeGroupBadgeProps {
  ageGroup: AgeGroup
}

export default function AgeGroupBadge({ ageGroup }: AgeGroupBadgeProps) {
  return (
    <span className="inline-flex min-h-6 shrink-0 items-center rounded-md border border-academy bg-academy/10 px-2 py-0.5 text-xs font-semibold leading-5 text-slate-800">
      {AGE_GROUP_LABELS[ageGroup]}
    </span>
  )
}
