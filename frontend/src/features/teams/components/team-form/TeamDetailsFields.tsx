import type { AgeGroup } from '../../types/team'

interface TeamDetailsFieldsProps {
  name: string
  ageGroup: AgeGroup | ''
  nameError?: string
  ageGroupError?: string
  disabled: boolean
  onNameChange: (name: string) => void
  onAgeGroupChange: (ageGroup: AgeGroup | '') => void
}

const ageGroups: { value: AgeGroup; label: string }[] = [
  { value: 'J', label: 'Juniors' },
  { value: 'U11', label: 'U11' },
  { value: 'U13', label: 'U13' },
  { value: 'U15', label: 'U15' },
]

export default function TeamDetailsFields({
  name,
  ageGroup,
  nameError,
  ageGroupError,
  disabled,
  onNameChange,
  onAgeGroupChange,
}: TeamDetailsFieldsProps) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <div>
        <label className="text-sm font-semibold text-slate-800" htmlFor="team-name">
          Team name
        </label>
        <input
          id="team-name"
          maxLength={200}
          disabled={disabled}
          aria-describedby={nameError ? 'team-name-error' : undefined}
          aria-invalid={nameError !== undefined}
          className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/40 disabled:bg-slate-100"
          value={name}
          onChange={(event) => onNameChange(event.target.value)}
        />
        {nameError ? (
          <p id="team-name-error" className="mt-2 text-sm font-medium text-red-800">
            {nameError}
          </p>
        ) : null}
      </div>
      <div>
        <label className="text-sm font-semibold text-slate-800" htmlFor="team-age-group">
          Age group
        </label>
        <select
          id="team-age-group"
          disabled={disabled}
          aria-describedby={ageGroupError ? 'team-age-error' : undefined}
          aria-invalid={ageGroupError !== undefined}
          className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/40 disabled:bg-slate-100"
          value={ageGroup}
          onChange={(event) =>
            onAgeGroupChange(event.target.value as AgeGroup | '')
          }
        >
          <option value="">Choose an age group</option>
          {ageGroups.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
        {ageGroupError ? (
          <p id="team-age-error" className="mt-2 text-sm font-medium text-red-800">
            {ageGroupError}
          </p>
        ) : null}
      </div>
    </div>
  )
}
