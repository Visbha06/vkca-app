import { Link } from 'react-router-dom'
import { CalendarIcon, PerformanceIcon, PlayersIcon } from '@shared/components/icons/NavIcons'
import HomeSchedule from './HomeSchedule'
import HomeSummary from './HomeSummary'

const quickActions = [
  { label: 'Add player', to: '/players?action=add', icon: <PlayersIcon className="size-5" /> },
  { label: 'Create match', to: '/teams', icon: <PerformanceIcon className="size-5" /> },
  { label: 'Schedule event', to: '/calendar', icon: <CalendarIcon className="size-5" /> },
]

export default function HomePage() {
  return (
    <div className="mx-auto w-full max-w-7xl">
      <header className="flex flex-col gap-6 border-b border-slate-200 pb-8 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 md:text-4xl" tabIndex={-1}>
            Good evening, Coach
          </h1>
          <p className="mt-2 max-w-2xl text-base leading-7 text-slate-600 md:text-lg">
            Here’s what’s happening at the academy.
          </p>
        </div>
        <nav aria-label="Quick actions" className="flex flex-wrap gap-3">
          {quickActions.map((action) => (
            <Link key={action.label} to={action.to} className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-academy bg-white px-4 py-2 text-sm font-semibold text-slate-900 transition-colors hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2">
              <span className="text-academy" aria-hidden="true">{action.icon}</span>
              {action.label}
            </Link>
          ))}
        </nav>
      </header>
      <HomeSummary />
      <HomeSchedule />
    </div>
  )
}
