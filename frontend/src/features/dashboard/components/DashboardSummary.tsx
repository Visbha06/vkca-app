import type { ReactNode } from 'react'
import {
  CalendarIcon,
  MatchIcon,
  PlayersIcon,
} from '@shared/components/icons/NavIcons'
import type {
  DashboardMatchSection,
  DashboardPlayerSection,
  DashboardSummary as DashboardSummaryData,
  DashboardTrainingSection,
} from '../types/dashboard'
import {
  dashboardAudience,
  dashboardParticipantLabel,
  formatDashboardDate,
  formatDashboardTime,
} from './dashboardFormatting'

interface DashboardSummaryProps {
  summary: DashboardSummaryData
  onRetry: () => void
}

interface SummaryCardProps {
  children: ReactNode
  icon: ReactNode
  title: string
}

function SummaryCard({ children, icon, title }: SummaryCardProps) {
  return (
    <div className="dashboard-summary-card flex min-w-0 gap-4 p-5 lg:p-6">
      <span
        aria-hidden="true"
        className="flex size-11 shrink-0 items-center justify-center rounded-full bg-academy text-slate-900"
      >
        {icon}
      </span>
      <div className="min-w-0">
        <h2 className="font-semibold text-slate-900">{title}</h2>
        {children}
      </div>
    </div>
  )
}

function SectionMessage({
  message,
  retryLabel,
  retryable,
  unavailable,
  onRetry,
}: {
  message: string
  retryLabel: string
  retryable: boolean
  unavailable: boolean
  onRetry: () => void
}) {
  return (
    <div
      role={unavailable ? 'alert' : undefined}
      className="mt-2 text-sm leading-6 text-slate-700"
    >
      <p>{message}</p>
      {retryable ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 min-h-11 rounded-lg border border-red-800 bg-white px-3 font-semibold text-red-900 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2"
        >
          {retryLabel}
        </button>
      ) : null}
    </div>
  )
}

function TrainingSummary({
  section,
  onRetry,
}: {
  section: DashboardTrainingSection
  onRetry: () => void
}) {
  if (section.status !== 'ready') {
    return (
      <SectionMessage
        message={section.message}
        retryLabel="Retry upcoming training"
        retryable={section.status === 'unavailable' && section.retryable}
        unavailable={section.status === 'unavailable'}
        onRetry={onRetry}
      />
    )
  }
  return (
    <>
      <p className="mt-1 font-semibold tabular-nums text-slate-800">
        {formatDashboardDate(section.data.event_date)} ·{' '}
        {formatDashboardTime(section.data)}
      </p>
      <p className="mt-1 text-sm text-slate-600">
        <span>{section.data.name}</span>
        <span> · {dashboardAudience(section.data)}</span>
      </p>
    </>
  )
}

function MatchSummary({
  section,
  onRetry,
}: {
  section: DashboardMatchSection
  onRetry: () => void
}) {
  if (section.status !== 'ready') {
    return (
      <SectionMessage
        message={section.message}
        retryLabel="Retry next match"
        retryable={section.status === 'unavailable' && section.retryable}
        unavailable={section.status === 'unavailable'}
        onRetry={onRetry}
      />
    )
  }
  return (
    <>
      <p className="mt-1 font-semibold tabular-nums text-slate-800">
        {formatDashboardDate(section.data.match_date)} · {section.data.format}
      </p>
      <p className="mt-1 text-sm text-slate-600">
        {dashboardParticipantLabel(section.data)}
      </p>
    </>
  )
}

function PlayerSummary({
  section,
  onRetry,
}: {
  section: DashboardPlayerSection
  onRetry: () => void
}) {
  if (section.status !== 'ready') {
    return (
      <SectionMessage
        message={section.message}
        retryLabel="Retry player summary"
        retryable={section.status === 'unavailable' && section.retryable}
        unavailable={section.status === 'unavailable'}
        onRetry={onRetry}
      />
    )
  }
  if (section.data.kind === 'active_player_count') {
    const teamLabel = section.data.team_count === 1 ? 'team' : 'teams'
    return (
      <>
        <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900">
          {section.data.count}
        </p>
        <p className="mt-1 text-sm text-slate-600">
          Across {section.data.team_count} {teamLabel}
        </p>
      </>
    )
  }
  const teamLabel = section.data.team_count === 1 ? 'team' : 'teams'
  return (
    <>
      <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900">
        {section.data.team_count} {teamLabel}
      </p>
      <p className="mt-1 text-sm text-slate-600">
        {section.data.team_names.join(', ')}
      </p>
    </>
  )
}

export default function DashboardSummary({
  summary,
  onRetry,
}: DashboardSummaryProps) {
  const playerTitle =
    summary.player_slot.status === 'ready' &&
    summary.player_slot.data.kind === 'player_teams'
      ? summary.player_slot.data.team_count === 1
        ? 'My team'
        : 'My teams'
      : 'Active players'

  return (
    <section
      aria-label="Academy summary"
      className="dashboard-summary-container py-8"
    >
      <div className="dashboard-summary-grid overflow-hidden rounded-xl border border-slate-200 bg-white">
        <SummaryCard
          icon={<CalendarIcon className="size-6" />}
          title="Upcoming training"
        >
          <TrainingSummary section={summary.training} onRetry={onRetry} />
        </SummaryCard>
        <SummaryCard
          icon={<MatchIcon className="size-6" />}
          title="Next match"
        >
          <MatchSummary section={summary.next_match} onRetry={onRetry} />
        </SummaryCard>
        <SummaryCard
          icon={<PlayersIcon className="size-6" />}
          title={playerTitle}
        >
          <PlayerSummary section={summary.player_slot} onRetry={onRetry} />
        </SummaryCard>
      </div>
    </section>
  )
}
