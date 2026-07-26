export interface MetadataRow {
  id: string
  key: string
  value: string
}

interface PlayerMetadataFieldsProps {
  rows: MetadataRow[]
  errors: Record<string, string>
  disabled: boolean
  onAdd: () => void
  onChange: (id: string, field: 'key' | 'value', value: string) => void
  onRemove: (id: string) => void
}

const inputClass =
  'min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 placeholder:text-slate-500 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/40 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500'

export default function PlayerMetadataFields({
  rows,
  errors,
  disabled,
  onAdd,
  onChange,
  onRemove,
}: PlayerMetadataFieldsProps) {
  return (
    <fieldset className="mt-6 border-t border-slate-200 pt-6">
      <legend className="font-bold text-slate-900">Additional metadata</legend>
      <p className="mt-1 max-w-prose text-sm leading-6 text-slate-600">
        Add optional key-value details such as a shirt number or preferred position.
      </p>

      <div className="mt-4 space-y-4">
        {rows.map((row, index) => {
          const errorId = `metadata-${row.id}-error`
          return (
            <div key={row.id}>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
                <div>
                  <label htmlFor={`metadata-${row.id}-key`} className="text-sm font-semibold text-slate-800">
                    Metadata key {index + 1}
                  </label>
                  <input
                    id={`metadata-${row.id}-key`}
                    value={row.key}
                    disabled={disabled}
                    aria-invalid={errors[row.id] !== undefined}
                    aria-describedby={errors[row.id] ? errorId : undefined}
                    className={`mt-2 ${inputClass}`}
                    placeholder="e.g. shirt_number"
                    onChange={(event) => onChange(row.id, 'key', event.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor={`metadata-${row.id}-value`} className="text-sm font-semibold text-slate-800">
                    Metadata value {index + 1}
                  </label>
                  <input
                    id={`metadata-${row.id}-value`}
                    value={row.value}
                    disabled={disabled}
                    aria-invalid={errors[row.id] !== undefined}
                    aria-describedby={errors[row.id] ? errorId : undefined}
                    className={`mt-2 ${inputClass}`}
                    placeholder="e.g. 18"
                    onChange={(event) => onChange(row.id, 'value', event.target.value)}
                  />
                </div>
                {rows.length > 1 ? (
                  <button
                    type="button"
                    disabled={disabled}
                    aria-label={`Remove metadata field ${index + 1}`}
                    className="inline-flex min-h-11 items-center justify-center rounded-lg border border-slate-300 px-3 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-slate-400"
                    onClick={() => onRemove(row.id)}
                  >
                    Remove
                  </button>
                ) : null}
              </div>
              {errors[row.id] ? (
                <p id={errorId} className="mt-2 text-sm font-medium text-red-800">
                  {errors[row.id]}
                </p>
              ) : null}
            </div>
          )
        })}
      </div>

      <button
        type="button"
        disabled={disabled}
        className="mt-4 inline-flex min-h-11 items-center justify-center rounded-lg border border-academy bg-white px-4 text-sm font-semibold text-slate-900 transition-colors hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
        onClick={onAdd}
      >
        Add metadata field
      </button>
    </fieldset>
  )
}
