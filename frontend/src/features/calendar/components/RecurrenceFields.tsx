import type {
  AcademyDate,
  CalendarRecurrence,
  RecurrenceFrequency,
  RecurrenceTermination,
} from '../types/calendar'
import type { CalendarFormErrors } from '../utils/calendarForm'

interface RecurrenceFieldsProps {
  value: CalendarRecurrence | null
  firstDate: AcademyDate
  errors: CalendarFormErrors
  disabled: boolean
  required?: boolean
  onChange: (value: CalendarRecurrence | null) => void
}

const defaultRecurrence: CalendarRecurrence = {
  frequency: 'weekly',
  termination: 'never',
  end_date: null,
  occurrence_count: null,
}

export default function RecurrenceFields({
  value,
  firstDate,
  errors,
  disabled,
  required = false,
  onChange,
}: RecurrenceFieldsProps) {
  function setFrequency(frequency: RecurrenceFrequency) {
    if (value === null) return
    onChange({ ...value, frequency })
  }

  function setTermination(termination: RecurrenceTermination) {
    if (value === null) return
    onChange({
      ...value,
      termination,
      end_date: termination === 'end_date' ? firstDate : null,
      occurrence_count: termination === 'occurrence_count' ? 2 : null,
    })
  }

  return (
    <fieldset className="border-t border-slate-200 pt-5">
      <legend className="text-sm font-semibold text-slate-900">Recurrence</legend>
      <label className="mt-3 flex min-h-11 items-center gap-3 text-sm font-semibold text-slate-800">
        <input
          type="checkbox"
          checked={value !== null}
          disabled={disabled || required}
          className="size-5 rounded border-slate-300 text-academy focus:ring-academy"
          onChange={(event) =>
            onChange(event.target.checked ? defaultRecurrence : null)
          }
        />
        {required ? 'Recurring series' : 'Repeat this event'}
      </label>

      {value !== null ? (
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-semibold text-slate-800">
            Repeats
            <select
              aria-label="Recurrence frequency"
              value={value.frequency}
              disabled={disabled}
              className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/40"
              onChange={(event) =>
                setFrequency(event.target.value as RecurrenceFrequency)
              }
            >
              <option value="weekly">Every week</option>
              <option value="yearly">Every year</option>
            </select>
          </label>
          <label className="text-sm font-semibold text-slate-800">
            Ends
            <select
              aria-label="Recurrence termination"
              value={value.termination}
              disabled={disabled}
              className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/40"
              onChange={(event) =>
                setTermination(event.target.value as RecurrenceTermination)
              }
            >
              <option value="never">Never ends</option>
              <option value="end_date">Ends on date</option>
              <option value="occurrence_count">Ends after count</option>
            </select>
          </label>
          {value.termination === 'end_date' ? (
            <label className="text-sm font-semibold text-slate-800 sm:col-span-2">
              Recurrence end date
              <input
                type="date"
                min={firstDate}
                value={value.end_date ?? ''}
                disabled={disabled}
                aria-invalid={errors.recurrence_end_date !== undefined}
                aria-describedby={
                  errors.recurrence_end_date === undefined
                    ? undefined
                    : 'calendar-recurrence-date-error'
                }
                className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 px-3 text-base text-slate-900 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/40"
                onChange={(event) =>
                  onChange({ ...value, end_date: event.target.value || null })
                }
              />
              {errors.recurrence_end_date !== undefined ? (
                <span id="calendar-recurrence-date-error" className="mt-1 block text-sm text-red-800">
                  {errors.recurrence_end_date}
                </span>
              ) : null}
            </label>
          ) : null}
          {value.termination === 'occurrence_count' ? (
            <label className="text-sm font-semibold text-slate-800 sm:col-span-2">
              Number of occurrences
              <input
                type="number"
                min="1"
                step="1"
                value={value.occurrence_count ?? ''}
                disabled={disabled}
                aria-invalid={errors.occurrence_count !== undefined}
                aria-describedby={
                  errors.occurrence_count === undefined
                    ? undefined
                    : 'calendar-recurrence-count-error'
                }
                className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 px-3 text-base text-slate-900 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/40"
                onChange={(event) =>
                  onChange({
                    ...value,
                    occurrence_count:
                      event.target.value === ''
                        ? null
                        : Number(event.target.value),
                  })
                }
              />
              {errors.occurrence_count !== undefined ? (
                <span id="calendar-recurrence-count-error" className="mt-1 block text-sm text-red-800">
                  {errors.occurrence_count}
                </span>
              ) : null}
            </label>
          ) : null}
        </div>
      ) : null}
    </fieldset>
  )
}
