import { useState } from 'react'
import { useAuth } from '@features/auth'
import Pagination from '@shared/components/navigation/Pagination'
import SuccessMessage from '@shared/components/feedback/SuccessMessage'
import CoachCardGrid from '../components/coach-directory/CoachCardGrid'
import CoachesPageHeader from '../components/coach-directory/CoachesPageHeader'
import CoachDetailsModal from '../components/coach-details/CoachDetailsModal'
import useCoachDirectory from '../hooks/useCoachDirectory'
import { fetchCoachDetails } from '../api/coachApi'
import type { CoachResponse } from '../types/coach'

export default function CoachesPage() {
  const { user } = useAuth()
  const { errorMessage, handleFilterChange, handlePageChange, handleRetry, isFetching, listRegionRef, result, status, successMessage } = useCoachDirectory()
  const canAddCoach = user?.role === 'head coach'
  const [selectedCoach, setSelectedCoach] = useState<CoachResponse | null>(null)
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

  return <section className="mx-auto w-full max-w-7xl"><CoachesPageHeader canAddCoach={canAddCoach} isFetching={isFetching} status={status} totalCoaches={result?.total_coaches} onAdd={() => undefined} onFilterChange={handleFilterChange} />{successMessage ? <SuccessMessage>{successMessage}</SuccessMessage> : null}<div ref={listRegionRef} tabIndex={-1} aria-busy={isFetching && result !== null} className="focus:outline-none">{errorMessage ? <div role="alert" className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-950"><span>{errorMessage}{result !== null ? ' Previous results are still shown.' : ''}</span><button type="button" className="min-h-11 rounded-lg border border-rose-300 bg-white px-4 font-semibold focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2" onClick={handleRetry}>Retry</button></div> : null}<CoachCardGrid coaches={coaches} showSkeletons={showInitialLoading} onSelect={handleSelectCoach} isCoachInteractive={canOpenCoach} isFiltered={status !== 'active'} /></div>{result !== null && result.total_pages > 1 ? <div className="mt-6"><Pagination ariaLabel="Coach pages" page={result.page} totalPages={result.total_pages} isLoading={isFetching} onPageChange={handlePageChange} /></div> : null}{selectedCoach !== null && user !== null ? <CoachDetailsModal coach={selectedCoach} currentUserRole={user.role} onClose={() => setSelectedCoach(null)} /> : null}</section>
}
