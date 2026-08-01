import type { AgeGroup, CalendarScope } from '../types/calendar'

interface EventScopeFieldsProps {
  value: CalendarScope
  errorMessage?: string
  disabled: boolean
  onChange: (value: CalendarScope) => void
}

const ageGroups: Array<{ value: AgeGroup; label: string }> = [
  { value: 'J', label: 'Juniors' },
  { value: 'U11', label: 'U11' },
  { value: 'U13', label: 'U13' },
  { value: 'U15', label: 'U15' },
]

export default function EventScopeFields({
  value,
  errorMessage,
  disabled,
  onChange,
}: EventScopeFieldsProps) {
  const allAcademy = value.scope_kind === 'all_academy'

  function toggleAgeGroup(ageGroup: AgeGroup) {
    const next = value.age_groups.includes(ageGroup)
      ? value.age_groups.filter((candidate) => candidate !== ageGroup)
      : [...value.age_groups, ageGroup]
    onChange({ scope_kind: 'age_group', age_groups: next })
  }

  return (
    <fieldset
      aria-describedby={errorMessage === undefined ? undefined : 'calendar-scope-error'}
      className="border-t border-slate-200 pt-5"
    >
      <legend className="text-sm font-semibold text-slate-900">Who is this for?</legend>
      <label className="mt-3 flex min-h-11 items-center gap-3 text-sm font-semibold text-slate-800">
        <input
          type="checkbox"
          checked={allAcademy}
          disabled={disabled}
          className="size-5 rounded border-slate-300 text-academy focus:ring-academy"
          onChange={(event) =>
            onChange(
              event.target.checked
                ? { scope_kind: 'all_academy', age_groups: [] }
                : { scope_kind: 'age_group', age_groups: [] },
            )
          }
        />
        All Academy
      </label>
      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {ageGroups.map((ageGroup) => (
          <label
            key={ageGroup.value}
            className="flex min-h-11 items-center gap-2 rounded-lg border border-slate-200 px-3 text-sm font-semibold text-slate-800"
          >
            <input
              type="checkbox"
              checked={value.age_groups.includes(ageGroup.value)}
              disabled={disabled || allAcademy}
              className="size-5 rounded border-slate-300 text-academy focus:ring-academy"
              onChange={() => toggleAgeGroup(ageGroup.value)}
            />
            {ageGroup.label}
          </label>
        ))}
      </div>
      {errorMessage !== undefined ? (
        <p id="calendar-scope-error" className="mt-2 text-sm text-red-800">
          {errorMessage}
        </p>
      ) : null}
    </fieldset>
  )
}
