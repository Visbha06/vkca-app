import CoachStatusFilter from './CoachStatusFilter'
import type { CoachStatusFilterValue } from '../../types/coach'

interface CoachesPageHeaderProps {
  canAddCoach: boolean
  isFetching: boolean
  status: CoachStatusFilterValue
  totalCoaches?: number
  onAdd: () => void
  onFilterChange: (status: CoachStatusFilterValue) => void
}

export default function CoachesPageHeader({ canAddCoach, isFetching, status, totalCoaches, onAdd, onFilterChange }: CoachesPageHeaderProps) {
  const countCopy = totalCoaches === undefined ? null : isFetching ? 'Updating results…' : `${totalCoaches} ${status === 'active' ? 'active ' : ''}${totalCoaches === 1 ? 'coach' : 'coaches'}`
  return <><header className="flex flex-col gap-5 border-b border-slate-200 pb-6 sm:flex-row sm:items-end sm:justify-between"><div><h1 className="text-3xl font-bold tracking-tight text-slate-900 md:text-4xl" tabIndex={-1}>Coaches Portal</h1><p className="mt-2 max-w-2xl text-base leading-7 text-slate-600">Review coach accounts, team coverage, and current availability.</p></div>{canAddCoach ? <button type="button" className="inline-flex min-h-11 items-center justify-center rounded-lg border border-academy bg-white px-4 text-sm font-semibold text-slate-900 transition-colors hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2" onClick={onAdd}>Add Coach</button> : null}</header><div className="flex flex-col gap-4 py-6 sm:flex-row sm:flex-wrap sm:items-end"><CoachStatusFilter value={status} onFilterChange={onFilterChange} />{countCopy !== null ? <p aria-atomic="true" aria-live="polite" className="min-h-5 text-sm font-medium text-slate-600 sm:basis-full lg:ml-auto lg:flex lg:min-h-11 lg:basis-auto lg:items-center">{countCopy}</p> : null}</div></>
}
