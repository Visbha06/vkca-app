import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'
import DateOfBirthPicker from '@shared/components/forms/date-of-birth/DateOfBirthPicker'
import type {
  CalendarEventCreatePayload,
  EventType,
} from '../types/calendar'
import {
  normalizeCalendarForm,
  validateCalendarForm,
  type CalendarFormErrors,
} from '../utils/calendarForm'
import EventScopeFields from './EventScopeFields'
import RecurrenceFields from './RecurrenceFields'

interface EventFormProps {
  initialValues: CalendarEventCreatePayload
  academyToday: string
  allowRecurrence: boolean
  allowUnchangedPast?: boolean
  recurrenceRequired?: boolean
  isSubmitting: boolean
  isBlocked?: boolean
  errorMessage: string | null
  errorAction?: ReactNode
  submitLabel: string
  onCancel: () => void
  onChange?: () => void
  onDirtyChange: (isDirty: boolean) => void
  onSubmit: (values: CalendarEventCreatePayload) => void
}

const inputClassName =
  'mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/40 disabled:cursor-not-allowed disabled:bg-slate-100'

export default function EventForm({
  initialValues,
  academyToday,
  allowRecurrence,
  allowUnchangedPast = false,
  recurrenceRequired = false,
  isSubmitting,
  isBlocked = false,
  errorMessage,
  errorAction,
  submitLabel,
  onCancel,
  onChange,
  onDirtyChange,
  onSubmit,
}: EventFormProps) {
  const [values, setValues] = useState(initialValues)
  const [errors, setErrors] = useState<CalendarFormErrors>({})
  const formRef = useRef<HTMLFormElement>(null)
  const controlsDisabled = isSubmitting || isBlocked
  const latestAcademyDate = `${Number(academyToday.slice(0, 4)) + 100}-12-31`
  const initialFingerprint = useMemo(
    () => JSON.stringify(initialValues),
    [initialValues],
  )
  const isDirty = JSON.stringify(values) !== initialFingerprint

  useEffect(() => onDirtyChange(isDirty), [isDirty, onDirtyChange])

  function replace(next: CalendarEventCreatePayload) {
    setValues(next)
    setErrors({})
    onChange?.()
  }

  function setEventType(eventType: EventType) {
    replace({
      ...values,
      event_type: eventType,
      is_all_day: eventType === 'miscellaneous' ? values.is_all_day : false,
      start_time:
        eventType !== 'miscellaneous' && values.start_time === null
          ? '17:00'
          : values.start_time,
      end_time:
        eventType !== 'miscellaneous' && values.end_time === null
          ? '18:30'
          : values.end_time,
    })
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (controlsDisabled) return
    const nextErrors = validateCalendarForm(
      values,
      academyToday,
      allowRecurrence,
      allowUnchangedPast ? initialValues : undefined,
    )
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) {
      requestAnimationFrame(() =>
        formRef.current
          ?.querySelector<HTMLElement>('[aria-invalid="true"]')
          ?.focus(),
      )
      return
    }
    onSubmit(normalizeCalendarForm(values, allowRecurrence))
  }

  return (
    <form ref={formRef} noValidate aria-busy={isSubmitting} className="space-y-5 px-5 py-5 sm:px-6" onSubmit={handleSubmit}>
      {errorMessage !== null ? (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-950">
          {errorMessage}
          {errorAction}
        </div>
      ) : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-semibold text-slate-800">
          Event type
          <select
            value={values.event_type}
            disabled={controlsDisabled}
            className={inputClassName}
            onChange={(event) => setEventType(event.target.value as EventType)}
          >
            <option value="practice">Practice</option>
            <option value="game">Game</option>
            <option value="miscellaneous">Miscellaneous</option>
          </select>
        </label>
        <div className="text-sm font-semibold text-slate-800">
          <label htmlFor="calendar-event-date">Academy date</label>
          <DateOfBirthPicker
            id="calendar-event-date"
            label="academy date"
            value={values.event_date}
            disabled={controlsDisabled}
            earliest={academyToday}
            latest={latestAcademyDate}
            error={errors.event_date}
            errorId="calendar-date-error"
            onChange={(eventDate) =>
              replace({ ...values, event_date: eventDate })
            }
          />
          {errors.event_date ? <span id="calendar-date-error" className="mt-1 block text-sm text-red-800">{errors.event_date}</span> : null}
        </div>
      </div>
      <label className="block text-sm font-semibold text-slate-800">
        Event name
        <input
          id="calendar-event-name"
          type="text"
          maxLength={200}
          value={values.name}
          disabled={controlsDisabled}
          aria-invalid={errors.name !== undefined}
          aria-describedby={errors.name ? 'calendar-name-error' : undefined}
          className={inputClassName}
          onChange={(event) => replace({ ...values, name: event.target.value })}
        />
        {errors.name ? <span id="calendar-name-error" className="mt-1 block text-sm text-red-800">{errors.name}</span> : null}
      </label>

      {values.event_type === 'miscellaneous' ? (
        <label className="flex min-h-11 items-center gap-3 text-sm font-semibold text-slate-800">
          <input
            type="checkbox"
            checked={values.is_all_day}
            disabled={controlsDisabled}
            className="size-5 rounded border-slate-300 text-academy focus:ring-academy"
            onChange={(event) => replace({
              ...values,
              is_all_day: event.target.checked,
              start_time: event.target.checked ? null : '17:00',
              end_time: event.target.checked ? null : '18:30',
            })}
          />
          All-day event
        </label>
      ) : null}

      {!values.is_all_day ? (
        <div className="grid gap-4 sm:grid-cols-2" aria-describedby={errors.times ? 'calendar-times-error' : undefined}>
          <label className="text-sm font-semibold text-slate-800">Start time
            <input type="time" value={values.start_time ?? ''} disabled={controlsDisabled} aria-invalid={errors.times !== undefined} className={inputClassName} onChange={(event) => replace({ ...values, start_time: event.target.value || null })} />
          </label>
          <label className="text-sm font-semibold text-slate-800">End time
            <input type="time" value={values.end_time ?? ''} disabled={controlsDisabled} aria-invalid={errors.times !== undefined} className={inputClassName} onChange={(event) => replace({ ...values, end_time: event.target.value || null })} />
          </label>
          {errors.times ? <p id="calendar-times-error" className="text-sm text-red-800 sm:col-span-2">{errors.times}</p> : null}
        </div>
      ) : null}

      <EventScopeFields value={values.scope} errorMessage={errors.scope} disabled={controlsDisabled} onChange={(scope) => replace({ ...values, scope })} />
      {allowRecurrence ? (
        <RecurrenceFields value={values.recurrence} firstDate={values.event_date} errors={errors} disabled={controlsDisabled} required={recurrenceRequired} onChange={(recurrence) => replace({ ...values, recurrence })} />
      ) : null}
      <div className="flex flex-col-reverse gap-3 border-t border-slate-200 pt-5 sm:flex-row sm:justify-end">
        <button type="button" disabled={controlsDisabled} className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:text-slate-400" onClick={onCancel}>Cancel</button>
        <button type="submit" data-calendar-submit disabled={controlsDisabled} className="min-h-11 rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-400">
          {isSubmitting ? 'Saving event…' : submitLabel}
        </button>
      </div>
      {isSubmitting ? <p role="status" className="sr-only">Saving calendar event</p> : null}
    </form>
  )
}
