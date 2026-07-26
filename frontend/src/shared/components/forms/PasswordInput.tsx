import { useState } from 'react'
import PasswordVisibilityIcon from './PasswordVisibilityIcon'

interface PasswordInputProps {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  autoComplete?: string
  disabled?: boolean
  errors?: readonly string[]
}

export default function PasswordInput({
  id,
  label,
  value,
  onChange,
  autoComplete = 'new-password',
  disabled = false,
  errors = [],
}: PasswordInputProps) {
  const [visible, setVisible] = useState(false)
  const errorId = `${id}-errors`
  const toggleLabel = `${visible ? 'Hide' : 'Show'} ${label.toLowerCase()}`

  return (
    <div>
      <label className="text-sm font-semibold text-slate-800" htmlFor={id}>
        {label}
      </label>
      <div className="relative mt-2">
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          autoComplete={autoComplete}
          aria-describedby={errors.length > 0 ? errorId : undefined}
          aria-invalid={errors.length > 0 ? 'true' : undefined}
          className="min-h-11 w-full rounded-lg border border-slate-300 bg-white py-2 pl-3 pr-12 text-base text-slate-900 outline-none transition-colors focus:border-academy focus:ring-2 focus:ring-academy/40 disabled:cursor-not-allowed disabled:bg-slate-100"
          disabled={disabled}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
        <button
          type="button"
          aria-label={toggleLabel}
          className="absolute inset-y-0 right-0 flex min-w-11 items-center justify-center rounded-r-lg text-slate-600 transition-colors hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-academy disabled:cursor-not-allowed disabled:opacity-50"
          disabled={disabled}
          onClick={() => setVisible((current) => !current)}
        >
          <PasswordVisibilityIcon visible={visible} />
        </button>
      </div>
      {errors.length > 0 && (
        <ul id={errorId} className="mt-2 space-y-1 text-sm font-medium text-red-700">
          {errors.map((error) => <li key={error}>{error}</li>)}
        </ul>
      )}
    </div>
  )
}
