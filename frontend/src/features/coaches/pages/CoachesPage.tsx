import { useState } from 'react'
import { useAuth } from '@features/auth'
import Pagination from '@shared/components/navigation/Pagination'
import SuccessMessage from '@shared/components/feedback/SuccessMessage'
import CoachCardGrid from '../components/coach-directory/CoachCardGrid'
import CoachesPageHeader from '../components/coach-directory/CoachesPageHeader'
import CoachDetailsModal from '../components/coach-details/CoachDetailsModal'
import AddCoachModal from '../components/coach-form/AddCoachModal'
import TeamAssignmentsModal from '../components/coach-assignments/TeamAssignmentsModal'
import useCoachDirectory from '../hooks/useCoachDirectory'
import { fetchCoachDetails } from '../api/coachApi'
import type { CoachResponse } from '../types/coach'

export default function CoachesPage() {
  const { user } = useAuth()
  const {
    errorMessage,
    handleCoachAssignmentsChanged,
    handleCoachCreated,
    handleCoachReloaded,
    handleCoachStatusChanged,
    handleFilterChange,
    handlePageChange,
    handleRetry,
    isFetching,
    listRegionRef,
    result,
    status,
    successMessage,
  } = useCoachDirectory()
  const canAddCoach = user?.role === 'head coach'
  const [selectedCoach, setSelectedCoach] = useState<CoachResponse | null>(null)
  const [assignmentCoach, setAssignmentCoach] =
    useState<CoachResponse | null>(null)
  const [isAddCoachOpen, setIsAddCoachOpen] = useState(false)
  const showInitialLoading = isFetching && result === null
  const coaches = result?.coaches ?? []

  function canOpenCoach(coach: CoachResponse) {
    return user?.role !== 'assistant coach' || coach.is_active
  }

  function handleSelectCoach(coach: CoachResponse) {
    if (!canOpenCoach(coach)) return
    setSelectedCoach(coach)
    void fetchCoachDetails(coach.id)
      .then((details) => setSelectedCoach(details))
      .catch(() => undefined)
  }

  function handleStatusUpdate(
    coach: CoachResponse,
    announceStatus: boolean,
  ) {
    setSelectedCoach(coach)
    if (announceStatus) handleCoachStatusChanged(coach)
    else handleCoachReloaded(coach)
  }

  function handleEditAssignments(coach: CoachResponse) {
    setSelectedCoach(null)
    setAssignmentCoach(coach)
  }

  function handleAssignmentsSaved(coach: CoachResponse) {
    handleCoachAssignmentsChanged(coach)
    setAssignmentCoach(null)
  }

  return (
    <section className="mx-auto w-full max-w-7xl">
      <CoachesPageHeader
        canAddCoach={canAddCoach}
        isFetching={isFetching}
        status={status}
        totalCoaches={result?.total_coaches}
        onAdd={() => setIsAddCoachOpen(true)}
        onFilterChange={handleFilterChange}
      />
      {successMessage ? (
        <SuccessMessage>{successMessage}</SuccessMessage>
      ) : null}
      <div
        ref={listRegionRef}
        tabIndex={-1}
        aria-busy={isFetching && result !== null}
        className="focus:outline-none"
      >
        {errorMessage ? (
          <div
            role="alert"
            className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-950"
          >
            <span>
              {errorMessage}
              {result !== null ? ' Previous results are still shown.' : ''}
            </span>
            <button
              type="button"
              className="min-h-11 rounded-lg border border-rose-300 bg-white px-4 font-semibold focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
              onClick={handleRetry}
            >
              Retry
            </button>
          </div>
        ) : null}
        <CoachCardGrid
          coaches={coaches}
          showSkeletons={showInitialLoading}
          onSelect={handleSelectCoach}
          isCoachInteractive={canOpenCoach}
          isFiltered={status !== 'active'}
        />
      </div>
      {result !== null && result.total_pages > 1 ? (
        <div className="mt-6">
          <Pagination
            ariaLabel="Coach pages"
            page={result.page}
            totalPages={result.total_pages}
            isLoading={isFetching}
            onPageChange={handlePageChange}
          />
        </div>
      ) : null}
      {selectedCoach !== null && user !== null ? (
        <CoachDetailsModal
          coach={selectedCoach}
          currentUserId={user.id}
          currentUserRole={user.role}
          onClose={() => setSelectedCoach(null)}
          onCoachUpdated={(coach) => handleStatusUpdate(coach, true)}
          onCoachReloaded={(coach) => handleStatusUpdate(coach, false)}
          onEditAssignments={handleEditAssignments}
        />
      ) : null}
      {assignmentCoach !== null && user?.role === 'head coach' ? (
        <TeamAssignmentsModal
          coach={assignmentCoach}
          currentUserRole={user.role}
          onClose={() => setAssignmentCoach(null)}
          onCoachReloaded={handleCoachReloaded}
          onSaved={handleAssignmentsSaved}
        />
      ) : null}
      {isAddCoachOpen && canAddCoach ? (
        <AddCoachModal
          onClose={() => setIsAddCoachOpen(false)}
          onCreated={handleCoachCreated}
        />
      ) : null}
    </section>
  )
}
