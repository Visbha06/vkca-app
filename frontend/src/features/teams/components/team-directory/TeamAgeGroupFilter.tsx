import type { ChangeEvent } from 'react'
import type { AgeGroup } from '../../types/team'
import { AGE_GROUP_LABELS } from '../../utils/teamLabels'

interface TeamAgeGroupFilterProps {
  ageGroups: AgeGroup[]
  value: AgeGroup | null
  onChange: (ageGroup: AgeGroup | null) => void
}

export default function TeamAgeGroupFilter({
  ageGroups,
  value,
  onChange,
}: TeamAgeGroupFilterProps) {
  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    onChange(event.target.value === '' ? null : (event.target.value as AgeGroup))
  }

  return (
    <div className="w-full sm:w-auto sm:min-w-64">
      <label
        htmlFor="team-age-group-filter"
        className="mb-2 block text-sm font-semibold text-slate-800"
      >
        Filter by age group
      </label>
      <select
        id="team-age-group-filter"
        className="min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/40"
        value={value ?? ''}
        onChange={handleChange}
      >
        <option value="">All age groups</option>
        {ageGroups.map((ageGroup) => (
          <option key={ageGroup} value={ageGroup}>
            {AGE_GROUP_LABELS[ageGroup]}
          </option>
        ))}
      </select>
    </div>
  )
}
