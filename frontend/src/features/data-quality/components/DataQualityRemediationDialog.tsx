import ModalDialog from '@shared/components/overlays/ModalDialog'
import type { DataQualityFinding } from '../api/dataQualityApi'

interface DataQualityRemediationDialogProps {
  errorMessage?: string | null
  finding: DataQualityFinding
  isSubmitting: boolean
  onClose: () => void
  onConfirm: () => void
}

const actionCopy = {
  normalize_roster_order: {
    title: 'Normalize roster order?',
    description:
      'The current roster membership will stay the same. Only its persisted display order will become contiguous.',
    confirmLabel: 'Confirm normalization',
    pendingLabel: 'Normalizing roster…',
  },
  remove_inactive_player: {
    title: 'Remove inactive player from roster?',
    description:
      'Only this one player membership will be removed. Every other roster membership will stay unchanged.',
    confirmLabel: 'Confirm removal',
    pendingLabel: 'Removing player…',
  },
  remove_inactive_assistant_assignment: {
    title: 'Remove inactive Assistant Coach assignment?',
    description:
      'Only this one team assignment will be removed. The Assistant Coach and every other assignment will stay unchanged.',
    confirmLabel: 'Confirm removal',
    pendingLabel: 'Removing assignment…',
  },
}

export default function DataQualityRemediationDialog({
  errorMessage = null,
  finding,
  isSubmitting,
  onClose,
  onConfirm,
}: DataQualityRemediationDialogProps) {
  const remediation = finding.direct_remediation
  if (remediation === null) return null
  const copy = actionCopy[remediation.action]
  const isRemoval = remediation.action !== 'normalize_roster_order'

  function handleClose() {
    if (!isSubmitting) onClose()
  }

  return (
    <ModalDialog
      describedBy="data-quality-remediation-description"
      labelledBy="data-quality-remediation-title"
      onClose={handleClose}
      testId="data-quality-remediation-dialog"
    >
      <div aria-busy={isSubmitting} className="bg-white p-5 text-slate-900 sm:p-6">
        <h2
          id="data-quality-remediation-title"
          className="text-xl font-bold text-balance"
        >
          {copy.title}
        </h2>
        <p className="mt-3 font-semibold text-slate-900">
          {finding.entity_label}
        </p>
        <p
          id="data-quality-remediation-description"
          className="mt-2 max-w-prose text-sm leading-6 text-slate-700 text-pretty"
        >
          {copy.description}
        </p>
        {errorMessage !== null ? (
          <div
            role="alert"
            className="mt-5 rounded-lg border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-950"
          >
            {errorMessage}
          </div>
        ) : null}
        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            data-modal-initial-focus
            disabled={isSubmitting}
            className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-slate-400"
            onClick={handleClose}
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            className={
              isRemoval
                ? 'min-h-11 rounded-lg bg-red-800 px-4 text-sm font-semibold text-white hover:bg-red-900 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-red-300'
                : 'min-h-11 rounded-lg border border-academy bg-white px-4 text-sm font-semibold text-slate-800 hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400'
            }
            onClick={onConfirm}
          >
            {isSubmitting ? copy.pendingLabel : copy.confirmLabel}
          </button>
        </div>
        {isSubmitting ? (
          <p role="status" className="sr-only">
            Applying the confirmed remediation
          </p>
        ) : null}
      </div>
    </ModalDialog>
  )
}
