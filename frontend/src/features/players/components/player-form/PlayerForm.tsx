import {
  forwardRef,
  useImperativeHandle,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from 'react'
import { useUnsavedChanges } from '@shared/hooks/useUnsavedChanges'
import type { PlayerCreatePayload, PlayerResponse } from '../../types/player'
import PlayerFormFields, {
  type PlayerFieldErrors,
  type PlayerFormValues,
} from './PlayerFormFields'
import PlayerFormFeedback from './PlayerFormFeedback'
import PlayerMetadataFields, {
  type MetadataRow,
} from './PlayerMetadataFields'
import {
  playerFormIsDirty,
  playerFormPayload,
  playerFormValues,
  playerMetadataRows,
} from './playerFormState'

export interface PlayerFormHandle {
  requestClose: () => boolean
}

interface PlayerFormProps {
  onSubmit: (payload: PlayerCreatePayload) => Promise<void> | void
  onCancel: () => void
  isSubmitting?: boolean
  errorMessage?: string | null
  errorAction?: ReactNode
  onChange?: () => void
  player?: PlayerResponse
}

function validateFields(values: PlayerFormValues): PlayerFieldErrors {
  return {
    ...(!values.firstName.trim() ? { firstName: 'Enter a first name.' } : {}),
    ...(!values.lastName.trim() ? { lastName: 'Enter a last name.' } : {}),
    ...(!values.dateOfBirth ? { dateOfBirth: 'Choose a date of birth.' } : {}),
    ...(!values.battingStyle ? { battingStyle: 'Choose a batting style.' } : {}),
    ...(!values.bowlingStyle ? { bowlingStyle: 'Choose a bowling style.' } : {}),
    ...(!values.playerType ? { playerType: 'Choose a player type.' } : {}),
  }
}

function validateMetadata(rows: MetadataRow[]) {
  const errors: Record<string, string> = {}
  const seenKeys = new Set<string>()
  for (const row of rows) {
    const key = row.key.trim()
    if (!key && row.value.trim()) {
      errors[row.id] = 'Enter a key for this metadata value.'
    } else if (key && seenKeys.has(key)) {
      errors[row.id] = 'Metadata keys must be unique.'
    }
    if (key) seenKeys.add(key)
  }
  return errors
}

const PlayerForm = forwardRef<PlayerFormHandle, PlayerFormProps>(
  function PlayerForm(
    {
      onSubmit,
      onCancel,
      isSubmitting = false,
      errorMessage = null,
      errorAction,
      onChange,
      player,
    },
    ref,
  ) {
    const initialValues = playerFormValues(player)
    const initialMetadataRows = playerMetadataRows(player)
    const [values, setValues] = useState(initialValues)
    const [metadataRows, setMetadataRows] =
      useState<MetadataRow[]>(initialMetadataRows)
    const [fieldErrors, setFieldErrors] = useState<PlayerFieldErrors>({})
    const [metadataErrors, setMetadataErrors] = useState<Record<string, string>>({})
    const nextMetadataId = useRef(initialMetadataRows.length + 1)
    const isDirty = playerFormIsDirty(
      values,
      metadataRows,
      initialValues,
      initialMetadataRows,
    )
    const requestClose = useUnsavedChanges(isDirty, onCancel)
    useImperativeHandle(ref, () => ({ requestClose }), [requestClose])
    const isEditing = player !== undefined

    function updateField<Key extends keyof PlayerFormValues>(
      field: Key,
      value: PlayerFormValues[Key],
    ) {
      setValues((current) => ({ ...current, [field]: value }))
      setFieldErrors((current) => ({ ...current, [field]: undefined }))
      onChange?.()
    }

    function updateMetadata(id: string, field: 'key' | 'value', value: string) {
      setMetadataRows((rows) =>
        rows.map((row) => (row.id === id ? { ...row, [field]: value } : row)),
      )
      setMetadataErrors((current) => {
        const next = { ...current }
        delete next[id]
        return next
      })
      onChange?.()
    }

    function addMetadataRow() {
      const id = `metadata-${nextMetadataId.current++}`
      setMetadataRows((rows) => [...rows, { id, key: '', value: '' }])
    }

    function removeMetadataRow(id: string) {
      setMetadataRows((rows) => rows.filter((row) => row.id !== id))
      onChange?.()
    }

    function handleSubmit(event: FormEvent<HTMLFormElement>) {
      event.preventDefault()
      if (isSubmitting) return
      const nextFieldErrors = validateFields(values)
      const nextMetadataErrors = validateMetadata(metadataRows)
      setFieldErrors(nextFieldErrors)
      setMetadataErrors(nextMetadataErrors)
      if (
        Object.keys(nextFieldErrors).length > 0 ||
        Object.keys(nextMetadataErrors).length > 0
      ) return

      void onSubmit(playerFormPayload(values, metadataRows, player))
    }

    return (
      <form noValidate onSubmit={handleSubmit}>
        <div className="p-5 sm:p-6">
          <PlayerFormFeedback
            action={errorAction}
            message={errorMessage}
          />
          {isSubmitting ? (
            <span role="status" className="sr-only">
              {isEditing ? 'Updating player' : 'Creating player'}
            </span>
          ) : null}
          <PlayerFormFields
            values={values}
            errors={fieldErrors}
            disabled={isSubmitting}
            onChange={updateField}
          />
          <PlayerMetadataFields
            rows={metadataRows}
            errors={metadataErrors}
            disabled={isSubmitting}
            onAdd={addMetadataRow}
            onChange={updateMetadata}
            onRemove={removeMetadataRow}
          />
        </div>

        <div className="flex flex-col-reverse gap-3 border-t border-slate-200 p-5 sm:flex-row sm:justify-end sm:p-6">
          <button
            type="button"
            disabled={isSubmitting}
            className="inline-flex min-h-11 items-center justify-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 transition-colors hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-slate-400"
            onClick={requestClose}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex min-h-11 items-center justify-center rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white transition-colors hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {isSubmitting
              ? isEditing
                ? 'Saving changes…'
                : 'Creating player…'
              : isEditing
                ? 'Save changes'
                : 'Create player'}
          </button>
        </div>
      </form>
    )
  },
)

export default PlayerForm
