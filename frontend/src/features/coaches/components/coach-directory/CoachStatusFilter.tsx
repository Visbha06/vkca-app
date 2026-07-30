import type { CoachStatusFilterValue } from '../../types/coach'

interface CoachStatusFilterProps {
  value: CoachStatusFilterValue
  onFilterChange: (status: CoachStatusFilterValue) => void
}

export default function CoachStatusFilter({ value, onFilterChange }: CoachStatusFilterProps) {
  return <label className="flex min-w-48 flex-col gap-2 text-sm font-semibold text-slate-800">Coach status<select aria-label="Coach status" className="min-h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-900 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2" value={value} onChange={(event) => onFilterChange(event.target.value as CoachStatusFilterValue)}><option value="active">Active</option><option value="inactive">Inactive</option><option value="all">All</option></select></label>
}
