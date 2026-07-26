import { useEffect, useRef } from 'react'

interface ConfirmationDialogProps {
  onContinueEditing: () => void
  onDiscard: () => void
}

export default function ConfirmationDialog({
  onContinueEditing,
  onDiscard,
}: ConfirmationDialogProps) {
  const continueButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    continueButtonRef.current?.focus()
  }, [])

  return (
    <div role="alertdialog" aria-labelledby="unsaved-changes-title" className="bg-white p-5 text-slate-900 sm:p-6">
      <h2 id="unsaved-changes-title" className="text-xl font-bold">
        You have unsaved changes
      </h2>
      <p className="mt-2 max-w-prose text-sm leading-6 text-slate-700">
        Discarding will remove the team changes you have made in this form.
      </p>
      <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <button
          ref={continueButtonRef}
          type="button"
          data-modal-initial-focus
          className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
          onClick={onContinueEditing}
        >
          Continue editing
        </button>
        <button
          type="button"
          className="min-h-11 rounded-lg bg-red-800 px-4 text-sm font-semibold text-white hover:bg-red-900 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2"
          onClick={onDiscard}
        >
          Discard changes
        </button>
      </div>
    </div>
  )
}
