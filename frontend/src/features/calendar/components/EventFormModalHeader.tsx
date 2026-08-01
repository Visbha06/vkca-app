interface EventFormModalHeaderProps {
  isCreating: boolean
  isRecurring: boolean
  target: 'occurrence' | 'series'
  disabled: boolean
  onTargetChange: (target: 'occurrence' | 'series') => void
  onClose: () => void
}

export default function EventFormModalHeader({
  isCreating,
  isRecurring,
  target,
  disabled,
  onTargetChange,
  onClose,
}: EventFormModalHeaderProps) {
  return (
    <>
      <header className="border-b border-slate-200 px-5 py-4 pr-16 sm:px-6">
        <h2 id="calendar-event-form-title" className="text-xl font-bold">
          {isCreating ? 'Create event' : 'Edit event'}
        </h2>
        <p
          id="calendar-event-form-description"
          className="mt-1 text-sm text-slate-600"
        >
          Academy dates and times use America/Los_Angeles.
        </p>
      </header>
      {isRecurring ? (
        <fieldset className="mx-5 mt-5 grid gap-2 sm:mx-6 sm:grid-cols-2">
          <legend className="mb-2 text-sm font-semibold text-slate-900">
            Apply changes to
          </legend>
          <label className="flex min-h-11 items-center gap-3 rounded-lg border border-slate-200 px-3 text-sm text-slate-800">
            <input type="radio" name="edit-target" checked={target === 'occurrence'} disabled={disabled} className="size-5 text-academy focus:ring-academy" onChange={() => onTargetChange('occurrence')} />
            This occurrence only
          </label>
          <label className="flex min-h-11 items-center gap-3 rounded-lg border border-slate-200 px-3 text-sm text-slate-800">
            <input type="radio" name="edit-target" checked={target === 'series'} disabled={disabled} className="size-5 text-academy focus:ring-academy" onChange={() => onTargetChange('series')} />
            Entire series
          </label>
        </fieldset>
      ) : null}
      <button type="button" aria-label={isCreating ? 'Close create event' : 'Close edit event'} data-modal-initial-focus disabled={disabled} className="absolute right-3 top-3 flex size-11 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:text-slate-400 sm:right-4 sm:top-4" onClick={onClose}>
        <svg aria-hidden="true" className="size-6" fill="none" viewBox="0 0 24 24"><path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeLinecap="round" strokeWidth="2" /></svg>
      </button>
    </>
  )
}
