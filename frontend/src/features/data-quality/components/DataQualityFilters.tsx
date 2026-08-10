import type { DataQualityFiltersState } from '../types/dataQuality'
import {
  DATA_QUALITY_RULE_GROUPS,
  getDataQualityRulesForDomain,
} from '../utils/dataQualityRulePresentation'

interface DataQualityFiltersProps {
  filters: DataQualityFiltersState
  onChange: (field: keyof DataQualityFiltersState, value: string) => void
  onClear: () => void
}

const controlClass = 'min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm font-normal text-slate-900 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2'

export default function DataQualityFilters({ filters, onChange, onClear }: DataQualityFiltersProps) {
  const hasFilters = Object.values(filters).some((value) => value !== undefined)
  return (
    <section aria-label="Finding filters" className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white p-4 sm:p-5">
      <div className="grid min-w-0 grid-cols-1 items-end gap-3 sm:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(18rem,2fr)_auto]">
        <label className="grid min-w-0 gap-2 text-sm font-semibold text-slate-800">
          Severity
          <select aria-label="Severity" className={controlClass} value={filters.severity ?? ''} onChange={(event) => onChange('severity', event.target.value)}>
            <option value="">All severities</option><option value="critical">Critical</option><option value="warning">Warning</option><option value="info">Info</option>
          </select>
        </label>
        <label className="grid min-w-0 gap-2 text-sm font-semibold text-slate-800">
          Domain
          <select aria-label="Domain" className={controlClass} value={filters.domain ?? ''} onChange={(event) => onChange('domain', event.target.value)}>
            <option value="">All domains</option><option value="players">Players</option><option value="teams">Teams</option><option value="rosters">Rosters</option><option value="coaches">Coaches</option><option value="calendar">Calendar</option>
          </select>
        </label>
        <label className="grid min-w-0 gap-2 text-sm font-semibold text-slate-800">
          Rule
          <select aria-label="Rule" className={controlClass} value={filters.ruleId ?? ''} onChange={(event) => onChange('ruleId', event.target.value)}>
            <option value="">All rules</option>
            {DATA_QUALITY_RULE_GROUPS.map((group) => (
              <optgroup key={group.domain} label={group.label}>
                {getDataQualityRulesForDomain(group.domain).map(
                  ([ruleId, presentation]) => (
                    <option key={ruleId} value={ruleId}>
                      {presentation.label}
                    </option>
                  ),
                )}
              </optgroup>
            ))}
          </select>
        </label>
        <button type="button" className="min-h-11 w-full rounded-lg border border-academy bg-white px-4 text-sm font-semibold whitespace-nowrap text-slate-900 transition-colors hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-50 disabled:text-slate-400 xl:w-auto" disabled={!hasFilters} onClick={onClear}>Clear filters</button>
      </div>
    </section>
  )
}
