import type { BusinessAuditEvent } from '../types/businessAudit'
import BusinessAuditEventItem from './BusinessAuditEventItem'

export default function BusinessAuditEventList({ events, isFetching }: { events: BusinessAuditEvent[]; isFetching: boolean }) {
  return <section aria-label="Business audit events" aria-busy={isFetching} className="rounded-xl border border-slate-200 bg-white p-5 sm:p-6"><ol className="divide-y divide-slate-200">{events.map((event) => <BusinessAuditEventItem key={event.id} event={event} />)}</ol></section>
}
