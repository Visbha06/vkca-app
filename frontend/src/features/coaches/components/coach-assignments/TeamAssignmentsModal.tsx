import { useCallback, useEffect, useMemo, useState } from 'react'
import type { UserRole } from '@features/auth/types/auth'
import { fetchTeams } from '@features/teams/api/teamApi'
import type { TeamResponse } from '@features/teams/types/team'
import { ApiClientError } from '@shared/api/client'
import ModalDialog from '@shared/components/overlays/ModalDialog'
import { useUnsavedChanges } from '@shared/hooks/useUnsavedChanges'
import { updateTeamAssignments } from '../../api/coachApi'
import type { CoachResponse } from '../../types/coach'
import useConflictHandler from '../../hooks/useConflictHandler'
import AssignmentCloseConfirmation from './AssignmentCloseConfirmation'
import TeamAssignmentsForm from './TeamAssignmentsForm'

interface TeamAssignmentsModalProps {
  coach: CoachResponse
  currentUserRole: UserRole
  onClose: () => void
  onCoachReloaded?: (coach: CoachResponse) => void
  onSaved: (coach: CoachResponse) => void
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError'
}

function TeamAssignmentsModalContent({
  coach,
  onClose,
  onCoachReloaded,
  onSaved,
}: TeamAssignmentsModalProps) {
  const [localCoach, setLocalCoach] = useState<CoachResponse | null>(null)
  const currentCoach =
    localCoach !== null &&
    localCoach.id === coach.id &&
    localCoach.version_number >= coach.version_number
      ? localCoach
      : coach
  const initialIds = useMemo(
    () => new Set(currentCoach.teams.map((team) => team.id)),
    [currentCoach.teams],
  )
  const [teams, setTeams] = useState<TeamResponse[]>([])
  const [selectedIds, setSelectedIds] = useState(() => new Set(initialIds))
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isConfirmingClose, setIsConfirmingClose] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)
  const {
    conflictMessage,
    handleConflict,
    isReloading,
    reloadCoach,
  } = useConflictHandler({
    coach: currentCoach,
    onCoachReloaded: (latestCoach) => {
      setLocalCoach(latestCoach)
      setSelectedIds(new Set(latestCoach.teams.map((team) => team.id)))
      setErrorMessage(null)
      onCoachReloaded?.(latestCoach)
    },
  })
  const isDirty =
    selectedIds.size !== initialIds.size ||
    [...selectedIds].some((id) => !initialIds.has(id))
  const requestClose = useUnsavedChanges(
    isDirty,
    onClose,
    () => setIsConfirmingClose(true),
  )

  useEffect(() => {
    const controller = new AbortController()
    void fetchTeams({ page: 1, pageSize: 100 }, controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) {
          setTeams(response.teams)
          setErrorMessage(null)
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && !isAbortError(error)) {
          setErrorMessage('Unable to load teams. Please try again.')
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false)
      })
    return () => controller.abort()
  }, [retryKey])

  const handleClose = useCallback(() => {
    if (isSubmitting) return
    if (isConfirmingClose) {
      setIsConfirmingClose(false)
      return
    }
    requestClose()
  }, [isConfirmingClose, isSubmitting, requestClose])

  function toggleTeam(teamId: string) {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(teamId)) next.delete(teamId)
      else next.add(teamId)
      return next
    })
    setErrorMessage(null)
  }

  function retryTeamLoad() {
    setIsLoading(true)
    setErrorMessage(null)
    setRetryKey((key) => key + 1)
  }

  async function handleSubmit() {
    if (isSubmitting || isLoading || !isDirty) return
    setIsSubmitting(true)
    setErrorMessage(null)
    try {
      const updatedCoach = await updateTeamAssignments(currentCoach.id, {
        team_ids: [...selectedIds],
        version_number: currentCoach.version_number,
      })
      onSaved(updatedCoach)
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 400) {
        setErrorMessage('Check the selected teams and try again.')
      } else if (error instanceof ApiClientError && error.status === 403) {
        setErrorMessage(
          'You do not have permission to edit team assignments.',
        )
      } else if (handleConflict(error)) {
        setErrorMessage(null)
      } else {
        setErrorMessage('Unable to save team assignments. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <ModalDialog
      labelledBy={
        isConfirmingClose
          ? 'assignment-unsaved-title'
          : 'team-assignments-title'
      }
      onClose={handleClose}
      testId="team-assignments-backdrop"
    >
      {isConfirmingClose ? (
        <AssignmentCloseConfirmation
          onContinueEditing={() => setIsConfirmingClose(false)}
          onDiscard={onClose}
        />
      ) : null}
      <TeamAssignmentsForm
        coachName={`${currentCoach.first_name} ${currentCoach.last_name}`}
        conflictMessage={conflictMessage}
        teams={teams}
        selectedTeamIds={selectedIds}
        errorMessage={errorMessage}
        isDirty={isDirty}
        isHidden={isConfirmingClose}
        isLoading={isLoading}
        isReloading={isReloading}
        isSubmitting={isSubmitting}
        onCancel={handleClose}
        onRetry={retryTeamLoad}
        onReload={() => void reloadCoach()}
        onSubmit={() => void handleSubmit()}
        onToggle={toggleTeam}
      />
    </ModalDialog>
  )
}

export default function TeamAssignmentsModal(
  props: TeamAssignmentsModalProps,
) {
  if (
    props.currentUserRole !== 'head coach' ||
    !props.coach.is_active
  ) {
    return null
  }
  return <TeamAssignmentsModalContent {...props} />
}
