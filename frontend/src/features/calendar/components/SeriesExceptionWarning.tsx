import { formatAcademyDateLabel, parseAcademyDate } from '@shared/utils/calendarDate'
import type { ExceptionRemovalWarningResponse } from '../types/calendar'

interface SeriesExceptionWarningProps {
  warning: ExceptionRemovalWarningResponse
  isSubmitting: boolean
  onCancel: () => void
  onContinue: () => void
}

function dateLabel(value: string) {
  const parsed = parseAcademyDate(value)
  return parsed === null ? value : formatAcademyDateLabel(parsed)
}

export default function SeriesExceptionWarning({
  warning,
  isSubmitting,
  onCancel,
  onContinue,
}: SeriesExceptionWarningProps) {
  return (
    <div role="alertdialog" aria-labelledby="series-exception-warning-title" className="bg-white p-5 text-slate-900 sm:p-6">
      <h2 id="series-exception-warning-title" className="text-xl font-bold">
        Remove saved occurrence changes?
      </h2>
      <p className="mt-2 max-w-prose text-sm leading-6 text-slate-700">
        {warning.detail} Continuing removes only the saved changes listed below.
      </p>
      <ul className="mt-4 divide-y divide-slate-200 border-y border-slate-200" aria-label="Occurrences with saved changes">
        {warning.removed_exception_original_dates.map((date) => (
          <li key={date} className="py-3 text-sm font-semibold text-slate-800">
            {dateLabel(date)}
          </li>
        ))}
      </ul>
      <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <button type="button" data-modal-initial-focus disabled={isSubmitting} className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:text-slate-400" onClick={onCancel}>
          Cancel
        </button>
        <button type="button" disabled={isSubmitting} className="min-h-11 rounded-lg bg-red-800 px-4 text-sm font-semibold text-white hover:bg-red-900 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2 disabled:bg-red-300" onClick={onContinue}>
          {isSubmitting ? 'Saving series…' : 'Continue and remove changes'}
        </button>
      </div>
      {isSubmitting ? <p role="status" className="sr-only">Saving series changes</p> : null}
    </div>
  )
}
