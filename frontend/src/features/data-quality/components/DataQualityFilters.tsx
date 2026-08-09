import type { DataQualityFiltersState } from '../types/dataQuality'

interface DataQualityFiltersProps {
  filters: DataQualityFiltersState
  onChange: (field: keyof DataQualityFiltersState, value: string) => void
  onClear: () => void
}

const ruleOptions = [
  'player.active_unassigned', 'player.inactive_rostered', 'player.normalized_identity_duplicate',
  'team.roster_below_minimum', 'team.roster_above_maximum', 'roster.order_non_positive',
  'roster.order_duplicate', 'roster.order_gap', 'roster.order_non_contiguous',
  'team.normalized_name_conflict', 'team.no_assigned_coach', 'coach.sole_head_coach_integrity',
  'coach.inactive_assigned', 'coach.active_assistant_unassigned', 'coach.assignment_invalid_role',
  'calendar.recurrence_end_before_start', 'calendar.stale_occurrence_exception',
]

const controlClass = 'min-h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2'

export default function DataQualityFilters({ filters, onChange, onClear }: DataQualityFiltersProps) {
  const hasFilters = Object.values(filters).some((value) => value !== undefined)
  return (
    <section aria-label="Finding filters" className="mt-6 rounded-xl border border-slate-200 bg-white p-4 sm:p-5">
      <div className="flex flex-wrap items-end gap-3">
        <label className="grid min-w-40 flex-1 gap-1 text-sm font-semibold text-slate-700">
          Severity
          <select aria-label="Severity" className={controlClass} value={filters.severity ?? ''} onChange={(event) => onChange('severity', event.target.value)}>
            <option value="">All severities</option><option value="critical">Critical</option><option value="warning">Warning</option><option value="info">Info</option>
          </select>
        </label>
        <label className="grid min-w-40 flex-1 gap-1 text-sm font-semibold text-slate-700">
          Domain
          <select aria-label="Domain" className={controlClass} value={filters.domain ?? ''} onChange={(event) => onChange('domain', event.target.value)}>
            <option value="">All domains</option><option value="players">Players</option><option value="teams">Teams</option><option value="rosters">Rosters</option><option value="coaches">Coaches</option><option value="calendar">Calendar</option>
          </select>
        </label>
        <label className="grid min-w-40 flex-1 gap-1 text-sm font-semibold text-slate-700">
          Rule
          <select aria-label="Rule" className={controlClass} value={filters.ruleId ?? ''} onChange={(event) => onChange('ruleId', event.target.value)}>
            <option value="">All rules</option>{ruleOptions.map((ruleId) => <option key={ruleId} value={ruleId}>{ruleId}</option>)}
          </select>
        </label>
        <button type="button" className="min-h-11 rounded-lg border border-academy bg-white px-4 text-sm font-semibold text-slate-800 transition-colors hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:border-slate-200 disabled:text-slate-400" disabled={!hasFilters} onClick={onClear}>Clear filters</button>
      </div>
    </section>
  )
}
