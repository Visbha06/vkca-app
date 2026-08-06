import Pagination from '@shared/components/navigation/Pagination'
import BusinessAuditEventList from '../components/BusinessAuditEventList'
import BusinessAuditFilters from '../components/BusinessAuditFilters'
import { BusinessAuditEmptyState, BusinessAuditErrorState, BusinessAuditLoadingState } from '../components/BusinessAuditStates'
import { useBusinessAudit, useBusinessAuditActorOptions } from '../hooks/useBusinessAudit'

export default function BusinessAuditLogPage() {
  const audit = useBusinessAudit()
  const actorOptions = useBusinessAuditActorOptions()
  const initialError = audit.errorMessage !== null && audit.result === null
  const eventCount = audit.result?.total_events ?? 0

  return <section className="mx-auto w-full max-w-7xl">
    <header className="mb-6"><h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">Audit Log</h1><p className="mt-2 max-w-3xl text-slate-600">Review safe, recorded academy activity from coaches and administrative workflows.</p></header>
    <BusinessAuditFilters actors={actorOptions.actors} actorErrorMessage={actorOptions.errorMessage} actorLoading={actorOptions.isLoading} filters={audit.filters} isFetching={audit.isFetching} onChange={audit.updateFilters} onClear={audit.clearFilters} onRetryActors={actorOptions.retry} />
    <p role="status" aria-live="polite" className="my-5 text-sm font-semibold text-slate-700">{audit.isFetching ? 'Updating academy activity…' : eventCount === 1 ? '1 event found' : `${eventCount} events found`}</p>
    {initialError ? <BusinessAuditErrorState onRetry={audit.retry} /> : <>{audit.isInitialLoading ? <BusinessAuditLoadingState /> : null}{audit.errorMessage !== null && audit.result !== null ? <div role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-950">Unable to update academy activity. Previous results are still shown. <button type="button" onClick={audit.retry} className="ml-2 min-h-11 rounded-lg border border-red-800 px-3 font-semibold hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2">Retry</button></div> : null}{audit.result !== null && audit.result.events.length === 0 ? <BusinessAuditEmptyState filtered={audit.hasFilters} onClear={audit.clearFilters} /> : null}{audit.result !== null && audit.result.events.length > 0 ? <BusinessAuditEventList events={audit.result.events} isFetching={audit.isFetching} /> : null}{audit.result !== null && audit.result.total_pages > 1 ? <div className="mt-8 border-t border-slate-200 pt-6"><Pagination ariaLabel="Audit log pages" page={audit.page} totalPages={audit.result.total_pages} isLoading={audit.isFetching} onPageChange={audit.changePage} /></div> : null}</>}
  </section>
}
