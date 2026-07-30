import { useState } from 'react'

interface TemporaryPasswordDisplayProps {
  coachName: string
  password: string
  onDone: () => void
}

export default function TemporaryPasswordDisplay({
  coachName,
  password,
  onDone,
}: TemporaryPasswordDisplayProps) {
  const [copyStatus, setCopyStatus] = useState<string | null>(null)

  async function copyPassword() {
    try {
      await navigator.clipboard.writeText(password)
      setCopyStatus('Password copied')
    } catch {
      setCopyStatus('Copy unavailable. Select and copy the password manually.')
    }
  }

  return (
    <div className="p-5 text-slate-900 sm:p-6">
      <h2 id="add-coach-title" className="text-xl font-bold">
        Assistant Coach created
      </h2>
      <p className="mt-2 max-w-prose text-sm leading-6 text-slate-700">
        Share this temporary password securely with {coachName}.
      </p>

      <div
        role="note"
        className="mt-5 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950"
      >
        <p className="font-bold">This password will only be shown once</p>
        <p className="mt-1">
          Copy it before closing this window. It cannot be retrieved later.
        </p>
      </div>

      <label className="mt-5 block text-sm font-semibold text-slate-800">
        Temporary password
        <input
          readOnly
          value={password}
          className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-slate-50 px-3 font-mono text-base text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy"
          onFocus={(event) => event.currentTarget.select()}
        />
      </label>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          className="min-h-11 rounded-lg border border-academy bg-white px-4 text-sm font-semibold text-slate-900 hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
          onClick={() => void copyPassword()}
        >
          Copy password
        </button>
        {copyStatus !== null ? (
          <p aria-live="polite" className="text-sm font-medium text-slate-700">
            {copyStatus}
          </p>
        ) : null}
      </div>

      <div className="mt-6 flex justify-end border-t border-slate-200 pt-5">
        <button
          type="button"
          className="min-h-11 rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
          onClick={onDone}
        >
          Done
        </button>
      </div>
    </div>
  )
}
