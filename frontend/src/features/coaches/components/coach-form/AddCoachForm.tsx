import { useEffect, useState, type FormEvent } from 'react'
import type { TeamResponse } from '@features/teams/types/team'
import type { CoachCreatePayload } from '../../types/coach'
import CoachIdentityFields from './CoachIdentityFields'
import CoachTeamSelector from './CoachTeamSelector'

interface AddCoachFormProps {
  teams: TeamResponse[]
  teamsError: string | null
  emailError: string | null
  errorMessage: string | null
  isLoadingTeams: boolean
  isSubmitting: boolean
  onCancel: () => void
  onChange: () => void
  onDirtyChange: (isDirty: boolean) => void
  onSubmit: (payload: CoachCreatePayload) => Promise<void> | void
}

interface FormErrors {
  firstName?: string
  lastName?: string
  email?: string
}

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export default function AddCoachForm({
  teams,
  teamsError,
  emailError,
  errorMessage,
  isLoadingTeams,
  isSubmitting,
  onCancel,
  onChange,
  onDirtyChange,
  onSubmit,
}: AddCoachFormProps) {
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [teamIds, setTeamIds] = useState<string[]>([])
  const [errors, setErrors] = useState<FormErrors>({})
  const isDirty =
    firstName !== '' || lastName !== '' || email !== '' || teamIds.length > 0

  useEffect(() => {
    onDirtyChange(isDirty)
  }, [isDirty, onDirtyChange])

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (isSubmitting) return
    const normalizedEmail = email.trim().toLowerCase()
    const nextErrors: FormErrors = {
      ...(!firstName.trim() ? { firstName: 'Enter a first name.' } : {}),
      ...(!lastName.trim() ? { lastName: 'Enter a last name.' } : {}),
      ...(!normalizedEmail
        ? { email: 'Enter an email address.' }
        : !emailPattern.test(normalizedEmail)
          ? { email: 'Enter a valid email address.' }
          : {}),
    }
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return
    void onSubmit({
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      email: normalizedEmail,
      ...(teamIds.length === 0 ? {} : { team_ids: teamIds }),
    })
  }

  function updateField(
    field: keyof FormErrors,
    value: string,
    setter: (nextValue: string) => void,
  ) {
    setter(value)
    setErrors((current) => ({ ...current, [field]: undefined }))
    onChange()
  }

  function toggleTeam(teamId: string) {
    setTeamIds((current) =>
      current.includes(teamId)
        ? current.filter((id) => id !== teamId)
        : [...current, teamId],
    )
    onChange()
  }

  const resolvedEmailError = errors.email ?? emailError

  return (
    <form noValidate onSubmit={handleSubmit}>
      <div className="space-y-5 p-5 sm:p-6">
        {errorMessage !== null ? (
          <div
            role="alert"
            className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-950"
          >
            {errorMessage}
          </div>
        ) : null}
        {isSubmitting ? (
          <span role="status" className="sr-only">
            Creating coach
          </span>
        ) : null}

        <CoachIdentityFields
          firstName={firstName}
          lastName={lastName}
          email={email}
          firstNameError={errors.firstName}
          lastNameError={errors.lastName}
          emailError={resolvedEmailError}
          isDisabled={isSubmitting}
          onFirstNameChange={(value) =>
            updateField('firstName', value, setFirstName)
          }
          onLastNameChange={(value) =>
            updateField('lastName', value, setLastName)
          }
          onEmailChange={(value) => updateField('email', value, setEmail)}
        />

        <CoachTeamSelector
          teams={teams}
          selectedTeamIds={teamIds}
          errorMessage={teamsError}
          isLoading={isLoadingTeams}
          isDisabled={isSubmitting}
          onToggle={toggleTeam}
        />
      </div>

      <div className="flex flex-col-reverse gap-3 border-t border-slate-200 p-5 sm:flex-row sm:justify-end sm:p-6">
        <button
          type="button"
          disabled={isSubmitting}
          className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-slate-400"
          onClick={onCancel}
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="min-h-11 rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {isSubmitting ? 'Creating coach…' : 'Create coach'}
        </button>
      </div>
    </form>
  )
}
