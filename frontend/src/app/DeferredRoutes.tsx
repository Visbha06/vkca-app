import { lazy, Suspense, type ReactNode } from 'react'

const BusinessAuditLogPage = lazy(
  () => import('@features/audit/pages/BusinessAuditLogPage'),
)
const CalendarPage = lazy(() => import('@/pages/CalendarPage'))
const CoachesPage = lazy(() => import('@/pages/CoachesPage'))
const DataQualityPage = lazy(
  () => import('@features/data-quality/pages/DataQualityPage'),
)
const LoginPage = lazy(() => import('@features/auth/pages/LoginPage'))
const PlayersPage = lazy(() => import('@features/players/pages/PlayersPage'))
const SettingsPage = lazy(() => import('@features/settings/pages/SettingsPage'))
const TeamsPage = lazy(() => import('@features/teams/pages/TeamsPage'))

function RouteLoadingState() {
  return (
    <div
      role="status"
      aria-label="Loading page"
      className="mx-auto w-full max-w-7xl py-8"
    >
      <span className="sr-only">Loading page…</span>
      <div
        aria-hidden="true"
        className="h-32 rounded-xl border border-slate-200 bg-white motion-safe:animate-pulse"
      />
    </div>
  )
}

function DeferredRoute({ children }: { children: ReactNode }) {
  return <Suspense fallback={<RouteLoadingState />}>{children}</Suspense>
}

export function DeferredAuditLogRoute() {
  return (
    <DeferredRoute>
      <BusinessAuditLogPage />
    </DeferredRoute>
  )
}

export function DeferredCalendarRoute() {
  return (
    <DeferredRoute>
      <CalendarPage />
    </DeferredRoute>
  )
}

export function DeferredCoachesRoute() {
  return (
    <DeferredRoute>
      <CoachesPage />
    </DeferredRoute>
  )
}

export function DeferredDataQualityRoute() {
  return (
    <DeferredRoute>
      <DataQualityPage />
    </DeferredRoute>
  )
}

export function DeferredLoginRoute() {
  return (
    <DeferredRoute>
      <LoginPage />
    </DeferredRoute>
  )
}

export function DeferredPlayersRoute() {
  return (
    <DeferredRoute>
      <PlayersPage />
    </DeferredRoute>
  )
}

export function DeferredSettingsRoute() {
  return (
    <DeferredRoute>
      <SettingsPage />
    </DeferredRoute>
  )
}

export function DeferredTeamsRoute() {
  return (
    <DeferredRoute>
      <TeamsPage />
    </DeferredRoute>
  )
}
