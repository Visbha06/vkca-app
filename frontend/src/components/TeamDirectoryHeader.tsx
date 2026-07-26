import type { RefObject } from 'react'
import type { AgeGroup } from '../types/team'
import TeamAgeGroupFilter from './TeamAgeGroupFilter'
import TeamSearchField from './TeamSearchField'

interface TeamDirectoryHeaderProps {
  ageGroups: AgeGroup[]
  ageGroupFilter: AgeGroup | null
  canManageTeams: boolean
  isFetching: boolean
  resultCount?: number
  searchInputRef: RefObject<HTMLInputElement | null>
  searchQuery: string
  totalTeams?: number
  onAgeGroupChange: (ageGroup: AgeGroup | null) => void
  onCreate: () => void
  onSearchChange: (query: string) => void
}

export default function TeamDirectoryHeader({
  ageGroups,
  ageGroupFilter,
  canManageTeams,
  isFetching,
  resultCount,
  searchInputRef,
  searchQuery,
  totalTeams,
  onAgeGroupChange,
  onCreate,
  onSearchChange,
}: TeamDirectoryHeaderProps) {
  const hasActiveFilters = searchQuery.trim() !== '' || ageGroupFilter !== null
  const countCopy =
    totalTeams === undefined || resultCount === undefined
      ? null
      : isFetching
        ? 'Updating teams…'
        : hasActiveFilters
          ? `${resultCount} ${resultCount === 1 ? 'team' : 'teams'} found`
          : `${totalTeams} active ${totalTeams === 1 ? 'team' : 'teams'}`

  return (
    <>
      <header className="flex flex-col gap-5 border-b border-slate-200 pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1
            className="text-3xl font-bold tracking-tight text-slate-900 md:text-4xl"
            tabIndex={-1}
          >
            Teams
          </h1>
          <p className="mt-2 max-w-2xl text-base leading-7 text-slate-600">
            Organize academy squads and review their active rosters.
          </p>
        </div>
        {canManageTeams ? (
          <button
            type="button"
            className="inline-flex min-h-11 items-center justify-center rounded-lg border border-academy bg-white px-4 text-sm font-semibold text-slate-900 transition-colors hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
            onClick={onCreate}
          >
            Create Team
          </button>
        ) : null}
      </header>

      <div className="flex flex-col gap-4 py-6 sm:flex-row sm:flex-wrap sm:items-end">
        <TeamSearchField
          inputRef={searchInputRef}
          value={searchQuery}
          onChange={onSearchChange}
        />
        <TeamAgeGroupFilter
          ageGroups={ageGroups}
          value={ageGroupFilter}
          onChange={onAgeGroupChange}
        />
        {countCopy !== null ? (
          <p
            aria-atomic="true"
            aria-live="polite"
            className="min-h-5 text-sm font-medium text-slate-600 sm:basis-full lg:ml-auto lg:flex lg:min-h-11 lg:basis-auto lg:items-center"
          >
            {countCopy}
          </p>
        ) : null}
      </div>
    </>
  )
}
