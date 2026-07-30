import EmptyState from '@shared/components/feedback/EmptyState'
import type { CoachResponse } from '../../types/coach'
import CoachCard from './CoachCard'

interface CoachCardGridProps {
  coaches: CoachResponse[]
  showSkeletons: boolean
  onSelect: (coach: CoachResponse) => void
  isCoachInteractive?: (coach: CoachResponse) => boolean
  isFiltered?: boolean
}

function CoachCardSkeleton() {
  return <div className="min-h-32 animate-pulse rounded-xl border border-slate-200 bg-white p-3 motion-reduce:animate-none"><div className="flex gap-3"><div className="size-11 rounded-full bg-slate-200" /><div className="flex-1"><div className="h-5 w-2/3 rounded bg-slate-200" /><div className="mt-2 h-4 w-1/2 rounded bg-slate-200" /></div></div><div className="mt-3 h-5 w-1/3 rounded bg-slate-200" /></div>
}

export default function CoachCardGrid({ coaches, showSkeletons, onSelect, isCoachInteractive, isFiltered = false }: CoachCardGridProps) {
  if (showSkeletons) {
    return <div role="status" aria-live="polite"><span className="sr-only">Loading coaches</span><div aria-hidden="true" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }, (_, index) => <CoachCardSkeleton key={index} />)}</div></div>
  }

  if (coaches.length === 0) {
    return <EmptyState title={isFiltered ? 'No coaches match this status filter.' : 'No Assistant Coaches have been added yet.'} description={isFiltered ? 'Choose another status to view available coach accounts.' : 'Add an Assistant Coach when the academy is ready to expand its coaching team.'} />
  }

  return <ul aria-label="Coaches" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">{coaches.map((coach) => <li key={coach.id} className="h-full"><CoachCard coach={coach} interactive={isCoachInteractive?.(coach)} onSelect={onSelect} /></li>)}</ul>
}
