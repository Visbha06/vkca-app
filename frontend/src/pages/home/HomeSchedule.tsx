import { Link } from 'react-router-dom'
import { CalendarIcon, PerformanceIcon, PlayersIcon } from '@shared/components/icons/NavIcons'

const upcomingEvents = [
  ['21', 'Tue', '5:00 PM – 6:30 PM', 'Batting fundamentals – U15', 'Indoor Net 1 · 16 players', 'Training'],
  ['23', 'Thu', '4:30 PM – 6:00 PM', 'Bowling technique – U17', 'Outdoor Nets · 14 players', 'Training'],
  ['25', 'Sat', '10:30 AM – 1:30 PM', 'VKCA U14 vs Northside CC', 'Riverside Oval · 18 selected', 'Match'],
] as const

const recentActivity = [
  ['New player added', 'Aryan Patel joined U16', '2h ago', <PlayersIcon className="size-5" />],
  ['Performance recorded', 'Batting figures added for Vihaan Singh', '4h ago', <PerformanceIcon className="size-5" />],
  ['Event scheduled', 'Fielding session added for Monday at 4:00 PM', 'Yesterday', <CalendarIcon className="size-5" />],
  ['Player updated', 'Rhea Kapoor moved to the U14 squad', '2d ago', <PlayersIcon className="size-5" />],
] as const

function UpcomingEvents() {
  return (
    <section aria-labelledby="upcoming-events-heading" className="min-w-0 lg:col-span-2">
      <div className="flex items-center justify-between gap-4">
        <h2 id="upcoming-events-heading" className="text-xl font-bold text-slate-900">Upcoming events</h2>
        <Link to="/calendar" className="rounded-md px-2 py-1 text-sm font-semibold text-slate-700 underline decoration-academy decoration-2 underline-offset-4 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2">View calendar</Link>
      </div>
      <ul className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white">
        {upcomingEvents.map(([day, weekday, time, title, detail, category]) => (
          <li key={`${day}-${title}`} className="grid gap-4 border-b border-slate-200 p-5 last:border-b-0 sm:grid-cols-6 sm:items-center">
            <time className="flex items-baseline gap-2 sm:col-span-1 sm:block sm:text-center" dateTime={`2026-07-${day}`}>
              <span className="text-xs font-bold text-slate-600 sm:block">Jul</span>
              <span className="text-2xl font-bold tabular-nums text-slate-900 sm:block">{day}</span>
              <span className="text-xs font-semibold text-slate-600 sm:block">{weekday}</span>
            </time>
            <div className="min-w-0 sm:col-span-4">
              <p className="text-sm font-medium text-slate-600">{time}</p>
              <h3 className="mt-1 font-bold text-slate-900">{title}</h3>
              <p className="mt-1 text-sm text-slate-600">{detail}</p>
            </div>
            <span className="w-fit rounded-md border border-academy px-2.5 py-1 text-xs font-semibold text-slate-800 sm:col-span-1 sm:justify-self-end">{category}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function RecentActivity() {
  return (
    <section aria-labelledby="recent-activity-heading" className="min-w-0 lg:col-span-1 lg:border-l lg:border-slate-200 lg:pl-8">
      <h2 id="recent-activity-heading" className="text-xl font-bold text-slate-900">Recent academy activity</h2>
      <ol className="ml-5 mt-5 space-y-6 border-l border-slate-200 pl-5">
        {recentActivity.map(([title, detail, time, icon]) => (
          <li key={`${title}-${detail}`} className="relative flex min-w-0 gap-3">
            <span className="absolute -left-10 flex size-9 items-center justify-center rounded-full bg-academy text-slate-900 ring-4 ring-slate-50" aria-hidden="true">{icon}</span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <h3 className="font-semibold text-slate-900">{title}</h3>
                <span className="text-xs font-medium text-slate-500">{time}</span>
              </div>
              <p className="mt-1 text-sm leading-6 text-slate-600">{detail}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}

export default function HomeSchedule() {
  return <div className="grid gap-8 lg:grid-cols-3"><UpcomingEvents /><RecentActivity /></div>
}
