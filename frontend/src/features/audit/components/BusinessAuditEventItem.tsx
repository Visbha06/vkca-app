import { useId, useState } from 'react'
import { formatBusinessAuditTimestamp } from '../utils/businessAuditTime'
import type { BusinessAuditEvent } from '../types/businessAudit'

const categoryIcons: Record<BusinessAuditEvent['action_category'], string> = { coach: 'C', player: 'P', team: 'T', roster: 'R', calendar: 'K', scoring: 'S' }

function categoryLabel(category: string) { return `${category.slice(0, 1).toUpperCase()}${category.slice(1)}` }

export default function BusinessAuditEventItem({ event }: { event: BusinessAuditEvent }) {
  const [open, setOpen] = useState(false)
  const detailsId = useId()
  const details = [
    ['Action', event.action_type], ['Actor role', event.actor_role], ['Entity', event.target_entity_type], ['Target', event.target_label], ['Request ID', event.request_id],
  ].filter(([, value]) => value !== null)
  const metadata = Object.entries(event.metadata)
  const hasDetails = details.length > 0 || metadata.length > 0
  return <li className="flex min-w-0 flex-col gap-3 py-5 first:pt-0 last:pb-0 sm:flex-row sm:items-start sm:gap-4">
    <time dateTime={event.created_at} className="shrink-0 text-sm font-medium text-slate-500 sm:w-44">{formatBusinessAuditTimestamp(event.created_at)}</time>
    <div className="min-w-0 flex-1">
      <div className="flex flex-wrap items-center gap-2"><span aria-hidden="true" className="inline-flex size-7 items-center justify-center rounded-full bg-academy/20 text-xs font-bold text-slate-900">{categoryIcons[event.action_category]}</span><span className="rounded-md border border-academy bg-white px-2 py-1 text-xs font-semibold text-slate-800">{categoryLabel(event.action_category)}</span></div>
      <p className="mt-2 break-words font-semibold text-slate-900">{event.summary}</p>
      <p className="mt-1 break-words text-sm text-slate-600">{event.actor_display_name ?? 'System activity'}{event.target_label === null ? '' : ` · ${event.target_label}`}</p>
      {hasDetails ? <><button type="button" aria-expanded={open} aria-controls={detailsId} onClick={() => setOpen((current) => !current)} className="mt-3 min-h-11 rounded-lg border border-academy bg-white px-3 text-sm font-semibold text-slate-900 hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2">{open ? 'Hide safe details' : 'Show safe details'}</button>{open ? <dl id={detailsId} className="mt-3 grid gap-2 border-t border-slate-200 pt-3 text-sm sm:grid-cols-2">{details.map(([label, value]) => <div key={label}><dt className="font-semibold text-slate-700">{label}</dt><dd className="break-words text-slate-600">{value}</dd></div>)}{metadata.map(([key, value]) => <div key={key}><dt className="font-semibold text-slate-700">{key.replaceAll('_', ' ')}</dt><dd className="break-words text-slate-600">{Array.isArray(value) ? value.join(', ') : String(value)}</dd></div>)}</dl> : null}</> : null}
    </div>
  </li>
}
