import { useState } from 'react'
import DateOfBirthPicker from '@shared/components/forms/date-of-birth/DateOfBirthPicker'
import type {
  BusinessAuditActionType,
  BusinessAuditActorOption,
  BusinessAuditCategory,
  BusinessAuditEntityType,
  BusinessAuditFilters as Filters,
} from '../types/businessAudit'
import {
  BUSINESS_AUDIT_ACTION_TYPES,
  BUSINESS_AUDIT_CATEGORIES,
  BUSINESS_AUDIT_ENTITY_TYPES,
} from '../types/businessAudit'

interface BusinessAuditFiltersProps {
  actors: BusinessAuditActorOption[]
  actorErrorMessage: string | null
  actorLoading: boolean
  filters: Filters
  hasFilters: boolean
  onChange: (filters: Filters) => void
  onClear: () => void
  onRetryActors: () => void
}

function humanize(value: string) {
  return value.replaceAll('.', ' · ').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function pluralizeLabel(label: string) {
  if (/[^aeiou]y$/i.test(label)) return `${label.slice(0, -1)}ies`
  if (/(?:s|x|z|ch|sh)$/i.test(label)) return `${label}es`
  return `${label}s`
}

export default function BusinessAuditFilters({
  actors, actorErrorMessage, actorLoading, filters, hasFilters, onChange, onClear, onRetryActors,
}: BusinessAuditFiltersProps) {
  const [dateError, setDateError] = useState<string | null>(null)

  function update(next: Partial<Filters>) {
    const updated = { ...filters, ...next }
    const startDate = updated.startDate
    const endDate = updated.endDate
    if (startDate !== undefined && endDate !== undefined && endDate < startDate) {
      setDateError('End date must be on or after the start date.')
      return
    }
    setDateError(null)
    onChange(updated)
  }

  function clearFilters() {
    setDateError(null)
    onClear()
  }

  return (
    <section aria-labelledby="audit-filters-heading" className="rounded-xl border border-slate-200 bg-white p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 id="audit-filters-heading" className="text-lg font-bold text-slate-900">Filter activity</h2>
          <p className="mt-1 text-sm text-slate-600">Narrow the academy history by actor, action, item, or date.</p>
        </div>
        <button type="button" className="min-h-11 rounded-lg border border-academy bg-white px-4 text-sm font-semibold text-slate-900 transition-colors hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400" disabled={!hasFilters} onClick={clearFilters}>Clear filters</button>
      </div>
      <div className="mt-5 flex flex-wrap gap-4">
        <label className="min-w-0 flex-1 basis-48 text-sm font-semibold text-slate-800">Actor
          <select aria-label="Actor" value={filters.actorUserId ?? ''} disabled={actorLoading} onChange={(event) => update({ actorUserId: event.target.value || undefined })} className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm font-normal text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2">
            <option value="">All actors</option>
            {actors.map((actor) => <option key={actor.actor_user_id} value={actor.actor_user_id}>{actor.actor_display_name}{actor.actor_role === null ? '' : ` (${humanize(actor.actor_role)})`}</option>)}
          </select>
        </label>
        <SelectFilter label="Category" value={filters.actionCategory} values={BUSINESS_AUDIT_CATEGORIES} onChange={(value) => update({ actionCategory: value as BusinessAuditCategory | undefined })} />
        <SelectFilter label="Action" value={filters.actionType} values={BUSINESS_AUDIT_ACTION_TYPES} onChange={(value) => update({ actionType: value as BusinessAuditActionType | undefined })} />
        <SelectFilter label="Entity" value={filters.entityType} values={BUSINESS_AUDIT_ENTITY_TYPES} onChange={(value) => update({ entityType: value as BusinessAuditEntityType | undefined })} />
        <div data-audit-date-range className="flex min-w-full flex-col gap-4 sm:min-w-0 sm:flex-[2_1_21rem] sm:flex-row">
          <div className="min-w-0 flex-1 text-sm font-semibold text-slate-800">
            <label htmlFor="audit-start-date">Start date</label>
            <DateOfBirthPicker
              id="audit-start-date"
              label="start date"
              value={filters.startDate ?? ''}
              latest={filters.endDate}
              clearable
              triggerTextSize="sm"
              onChange={(value) => update({ startDate: value || undefined })}
            />
          </div>
          <div className="min-w-0 flex-1 text-sm font-semibold text-slate-800">
            <label htmlFor="audit-end-date">End date</label>
            <DateOfBirthPicker
              id="audit-end-date"
              label="end date"
              value={filters.endDate ?? ''}
              earliest={filters.startDate}
              clearable
              triggerTextSize="sm"
              onChange={(value) => update({ endDate: value || undefined })}
            />
          </div>
        </div>
      </div>
      {dateError !== null ? <p role="alert" className="mt-3 text-sm font-semibold text-red-800">{dateError}</p> : null}
      {actorErrorMessage !== null ? <div role="alert" className="mt-3 flex flex-wrap items-center gap-3 text-sm text-red-900"><span>{actorErrorMessage}</span><button type="button" onClick={onRetryActors} className="min-h-11 rounded-lg border border-red-800 px-3 font-semibold hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2">Retry actor options</button></div> : null}
    </section>
  )
}

function SelectFilter({ label, value, values, onChange }: { label: string; value: string | undefined; values: readonly string[]; onChange: (value: string | undefined) => void }) {
  return <label className="min-w-0 flex-1 basis-44 text-sm font-semibold text-slate-800">{label}<select aria-label={label} value={value ?? ''} onChange={(event) => onChange(event.target.value || undefined)} className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm font-normal text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"><option value="">All {pluralizeLabel(label.toLowerCase())}</option>{values.map((option) => <option key={option} value={option}>{humanize(option)}</option>)}</select></label>
}
