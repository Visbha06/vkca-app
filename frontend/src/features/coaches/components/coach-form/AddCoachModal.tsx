import { useCallback, useEffect, useState } from 'react'
import { fetchTeams } from '@features/teams/api/teamApi'
import type { TeamResponse } from '@features/teams/types/team'
import { ApiClientError } from '@shared/api/client'
import { isAbortError } from '@shared/api/errors'
import { useUnsavedChanges } from '@shared/hooks/useUnsavedChanges'
import ModalDialog from '@shared/components/overlays/ModalDialog'
import { createCoach } from '../../api/coachApi'
import type {
  CoachCreatePayload,
  CoachCreateResponse,
  CoachResponse,
} from '../../types/coach'
import AddCoachForm from './AddCoachForm'
import TemporaryPasswordDisplay from './TemporaryPasswordDisplay'

interface AddCoachModalProps {
  onClose: () => void
  onCreated: (coach: CoachResponse) => void
}

export default function AddCoachModal({
  onClose,
  onCreated,
}: AddCoachModalProps) {
  const [teams, setTeams] = useState<TeamResponse[]>([])
  const [isLoadingTeams, setIsLoadingTeams] = useState(true)
  const [teamsError, setTeamsError] = useState<string | null>(null)
  const [isDirty, setIsDirty] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [emailError, setEmailError] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [creation, setCreation] = useState<CoachCreateResponse | null>(null)
  const requestClose = useUnsavedChanges(isDirty, onClose)

  useEffect(() => {
    const controller = new AbortController()
    void fetchTeams({ page: 1, pageSize: 100 }, controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) {
          setTeams(response.teams)
          setTeamsError(null)
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && !isAbortError(error)) {
          setTeamsError(
            'Teams could not be loaded. You can still create the coach without an assignment.',
          )
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoadingTeams(false)
      })
    return () => controller.abort()
  }, [])

  const handleClose = useCallback(() => {
    if (isSubmitting) return
    if (creation !== null) {
      setCreation(null)
      onClose()
      return
    }
    requestClose()
  }, [creation, isSubmitting, onClose, requestClose])

  async function handleSubmit(payload: CoachCreatePayload) {
    if (isSubmitting) return
    setIsSubmitting(true)
    setEmailError(null)
    setErrorMessage(null)
    try {
      const response = await createCoach(payload)
      const coach: CoachResponse = {
        id: response.id,
        first_name: response.first_name,
        last_name: response.last_name,
        email: response.email,
        role: response.role,
        is_active: response.is_active,
        version_number: response.version_number,
        created_at: response.created_at,
        updated_at: response.updated_at,
        teams: response.teams,
      }
      setCreation(response)
      setIsDirty(false)
      onCreated(coach)
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 409) {
        setEmailError('An account with this email already exists.')
      } else if (error instanceof ApiClientError && error.status === 403) {
        setErrorMessage('You do not have permission to add coaches.')
      } else if (error instanceof ApiClientError && error.status === 400) {
        setErrorMessage(
          'Check the highlighted details and team assignments, then try again.',
        )
      } else {
        setErrorMessage('Unable to create the coach. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <ModalDialog
      labelledBy="add-coach-title"
      onClose={handleClose}
      testId="add-coach-backdrop"
    >
      {creation !== null ? (
        <TemporaryPasswordDisplay
          coachName={`${creation.first_name} ${creation.last_name}`}
          password={creation.temporary_password}
          onDone={handleClose}
        />
      ) : (
        <div className="relative bg-white text-slate-900">
          <header className="border-b border-slate-200 p-5 pr-16 sm:p-6 sm:pr-16">
            <h2 id="add-coach-title" className="text-xl font-bold">
              Add Assistant Coach
            </h2>
            <p className="mt-2 max-w-prose text-sm leading-6 text-slate-700">
              Create an active account and optionally assign its first teams.
            </p>
          </header>
          <AddCoachForm
            teams={teams}
            teamsError={teamsError}
            emailError={emailError}
            errorMessage={errorMessage}
            isLoadingTeams={isLoadingTeams}
            isSubmitting={isSubmitting}
            onCancel={handleClose}
            onChange={() => {
              setEmailError(null)
              setErrorMessage(null)
            }}
            onDirtyChange={setIsDirty}
            onSubmit={handleSubmit}
          />
          <button
            type="button"
            aria-label="Close add coach"
            data-modal-initial-focus
            disabled={isSubmitting}
            className="absolute right-3 top-3 flex size-11 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-slate-400 sm:right-4 sm:top-4"
            onClick={handleClose}
          >
            <svg
              aria-hidden="true"
              className="size-6"
              fill="none"
              viewBox="0 0 24 24"
            >
              <path
                d="m6 6 12 12M18 6 6 18"
                stroke="currentColor"
                strokeLinecap="round"
                strokeWidth="2"
              />
            </svg>
          </button>
        </div>
      )}
    </ModalDialog>
  )
}
