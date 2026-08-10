import type { components } from '../api/generated'

interface DataQualitySummaryProps {
  summary: components['schemas']['DataQualitySummary']
}

const countLabels = [
  ['Total', 'total_findings'],
  ['Critical', 'critical_count'],
  ['Warning', 'warning_count'],
  ['Info', 'info_count'],
] as const

export default function DataQualitySummary({ summary }: DataQualitySummaryProps) {
  return (
    <section aria-label="Academy health summary" className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <dl className="grid divide-y divide-slate-200 sm:grid-cols-4 sm:divide-x sm:divide-y-0">
        {countLabels.map(([label, key]) => (
          <div key={key} className="px-5 py-4">
            <dt className="text-sm font-semibold text-slate-700">{label}</dt>
            <dd className="mt-1 text-2xl font-bold text-slate-900">{summary[key]}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
