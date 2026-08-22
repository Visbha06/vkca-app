import { useEffect, useRef } from 'react'

interface UnsavedChangesPromptProps {
  title: string
  titleId: string
  description: string
  descriptionId: string
  onContinueEditing: () => void
  onDiscard: () => void
  continueEditingLabel?: string
  discardLabel?: string
}

export default function UnsavedChangesPrompt({
  title,
  titleId,
  description,
  descriptionId,
  onContinueEditing,
  onDiscard,
  continueEditingLabel = 'Continue editing',
  discardLabel = 'Discard changes',
}: UnsavedChangesPromptProps) {
  const continueButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    continueButtonRef.current?.focus()
  }, [])

  return (
    <div className="bg-white p-5 text-slate-900 sm:p-6">
      <h2 id={titleId} className="text-xl font-bold">
        {title}
      </h2>
      <p
        id={descriptionId}
        className="mt-2 max-w-prose text-sm leading-6 text-slate-700"
      >
        {description}
      </p>
      <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <button
          ref={continueButtonRef}
          type="button"
          data-modal-initial-focus
          className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
          onClick={onContinueEditing}
        >
          {continueEditingLabel}
        </button>
        <button
          type="button"
          className="min-h-11 rounded-lg bg-red-800 px-4 text-sm font-semibold text-white hover:bg-red-900 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2"
          onClick={onDiscard}
        >
          {discardLabel}
        </button>
      </div>
    </div>
  )
}
