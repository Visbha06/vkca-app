import { useCallback, useState } from 'react'
import { ApiClientError } from '@shared/api/client'
import {
  createTeam,
  fetchTeamRoster,
  fetchTeams,
  updateTeam,
} from '../../api/teamApi'
import { useUnsavedChanges } from '@shared/hooks/useUnsavedChanges'
import type {
  TeamCreatePayload,
  TeamResponse,
  TeamRosterResponse,
  TeamRosterSelection,
  TeamUpdatePayload,
} from '../../types/team'
import ConfirmationDialog from './ConfirmationDialog'
import ModalDialog from '@shared/components/overlays/ModalDialog'
import TeamConflictReloadButton from './TeamConflictReloadButton'
import TeamForm from './TeamForm'
import TeamFormModalHeader from './TeamFormModalHeader'
interface TeamFormModalProps {
  team?: TeamResponse
  roster?: TeamRosterResponse
  onClose: () => void
  onSaved: (team: TeamResponse) => void
  onPlayerInfo: (player: TeamRosterSelection) => void
}
const staleTeamMessage =
  'This team was updated by another coach. Reload the latest team before saving again.'

export default function TeamFormModal({
  team,
  roster,
  onClose,
  onSaved,
  onPlayerInfo,
}: TeamFormModalProps) {
  const [currentTeam, setCurrentTeam] = useState(team)
  const [currentRoster, setCurrentRoster] = useState(roster)
  const [formRevision, setFormRevision] = useState(0)
  const [isDirty, setIsDirty] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isReloading, setIsReloading] = useState(false)
  const [isConfirmingClose, setIsConfirmingClose] = useState(false)
  const [pendingPlayer, setPendingPlayer] = useState<TeamRosterSelection | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [hasStaleConflict, setHasStaleConflict] = useState(false)
  const isEditing = currentTeam !== undefined
  const showConfirmation = useCallback(() => {
    setIsConfirmingClose(true)
  }, [])
  const requestClose = useUnsavedChanges(
    isDirty,
    onClose,
    showConfirmation,
  )
  function handleModalClose() {
    if (isSubmitting || isReloading) return
    if (isConfirmingClose) {
      setPendingPlayer(null)
      setIsConfirmingClose(false)
      return
    }
    requestClose()
  }

  function handlePlayerInfo(player: TeamRosterSelection) {
    if (isDirty) {
      setPendingPlayer(player)
      setIsConfirmingClose(true)
      return
    }
    onPlayerInfo(player)
  }

  async function handleSubmit(
    payload: TeamCreatePayload | TeamUpdatePayload,
  ) {
    if (isSubmitting || isReloading) return
    setIsSubmitting(true)
    setErrorMessage(null)
    setHasStaleConflict(false)
    try {
      const savedTeam = currentTeam === undefined
        ? await createTeam(payload as TeamCreatePayload)
        : await updateTeam(currentTeam.id, payload as TeamUpdatePayload)
      onSaved(savedTeam)
      onClose()
    } catch (error) {
      if (
        error instanceof ApiClientError &&
        error.status === 409 &&
        /stale/i.test(error.message)
      ) {
        setHasStaleConflict(true)
        setErrorMessage(staleTeamMessage)
      } else if (error instanceof ApiClientError && error.status === 409) {
        setErrorMessage(
          'A team with this name already exists in the selected age group.',
        )
      } else if (error instanceof ApiClientError && error.status === 403) {
        setErrorMessage('You do not have permission to manage teams.')
      } else if (
        error instanceof ApiClientError &&
        (error.status === 400 || error.status === 404)
      ) {
        setErrorMessage(error.message)
      } else {
        setErrorMessage(
          `Unable to ${isEditing ? 'update' : 'create'} team. Please try again.`,
        )
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  async function reloadLatestTeam() {
    if (currentTeam === undefined || isReloading) return
    setIsReloading(true)
    try {
      const [teamsPage, latestRoster] = await Promise.all([
        fetchTeams({ page: 1, pageSize: 100 }),
        fetchTeamRoster(currentTeam.id),
      ])
      const latestTeam = teamsPage.teams.find(
        (candidate) => candidate.id === currentTeam.id,
      )
      if (latestTeam === undefined) {
        throw new Error('Team not found in latest results.')
      }
      setCurrentTeam(latestTeam)
      setCurrentRoster(latestRoster)
      setFormRevision((revision) => revision + 1)
      setIsDirty(false)
      setErrorMessage(null)
      setHasStaleConflict(false)
    } catch {
      setErrorMessage('Unable to reload the latest team. Please try again.')
    } finally {
      setIsReloading(false)
    }
  }

  const reloadAction = hasStaleConflict ? (
    <TeamConflictReloadButton
      isReloading={isReloading}
      onReload={reloadLatestTeam}
    />
  ) : undefined

  function discardChanges() {
    const player = pendingPlayer
    setPendingPlayer(null)
    if (player !== null) onPlayerInfo(player)
    else onClose()
  }

  return (
    <ModalDialog
      labelledBy={isConfirmingClose ? 'unsaved-changes-title' : 'team-form-title'}
      onClose={handleModalClose}
      testId="team-form-backdrop"
    >
      {isConfirmingClose ? (
        <ConfirmationDialog
          onContinueEditing={() => {
            setPendingPlayer(null)
            setIsConfirmingClose(false)
          }}
          onDiscard={discardChanges}
        />
      ) : null}
      <div
        hidden={isConfirmingClose}
        inert={isConfirmingClose ? true : undefined}
        className="relative bg-white text-slate-900"
      >
        <TeamFormModalHeader team={currentTeam} />
        <TeamForm
          key={`${currentTeam?.id ?? 'create'}-${currentTeam?.version_number ?? 0}-${formRevision}`}
          team={currentTeam}
          roster={currentRoster}
          isSubmitting={isSubmitting || isReloading}
          errorMessage={errorMessage}
          errorAction={reloadAction}
          onCancel={handleModalClose}
          onChange={() => {
            if (!hasStaleConflict) setErrorMessage(null)
          }}
          onDirtyChange={setIsDirty}
          onPlayerInfo={handlePlayerInfo}
          onSubmit={handleSubmit}
        />
        <button
          type="button"
          aria-label={isEditing ? 'Close edit team' : 'Close create team'}
          data-modal-initial-focus
          disabled={isSubmitting || isReloading}
          className="absolute right-3 top-3 flex size-11 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-slate-400 sm:right-4 sm:top-4"
          onClick={handleModalClose}
        >
          <svg aria-hidden="true" className="size-6" fill="none" viewBox="0 0 24 24">
            <path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
          </svg>
        </button>
      </div>
    </ModalDialog>
  )
}
