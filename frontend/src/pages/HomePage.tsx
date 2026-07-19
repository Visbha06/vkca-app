import { Link } from 'react-router-dom'
import {
  CalendarIcon,
  MatchIcon,
  PerformanceIcon,
  PlayersIcon,
} from '../components/NavIcons'

const upcomingEvents = [
  {
    day: '21',
    weekday: 'Tue',
    month: 'Jul',
    time: '5:00 PM – 6:30 PM',
    title: 'Batting fundamentals – U15',
    location: 'Indoor Net 1',
    attendance: '16 players',
    category: 'Training',
  },
  {
    day: '23',
    weekday: 'Thu',
    month: 'Jul',
    time: '4:30 PM – 6:00 PM',
    title: 'Bowling technique – U17',
    location: 'Outdoor Nets',
    attendance: '14 players',
    category: 'Training',
  },
  {
    day: '25',
    weekday: 'Sat',
    month: 'Jul',
    time: '10:30 AM – 1:30 PM',
    title: 'VKCA U14 vs Northside CC',
    location: 'Riverside Oval',
    attendance: '18 selected',
    category: 'Match',
  },
]

const recentActivity = [
  {
    title: 'New player added',
    detail: 'Aryan Patel joined U16',
    time: '2h ago',
    icon: <PlayersIcon className="size-5" />,
  },
  {
    title: 'Performance recorded',
    detail: 'Batting figures added for Vihaan Singh',
    time: '4h ago',
    icon: <PerformanceIcon className="size-5" />,
  },
  {
    title: 'Event scheduled',
    detail: 'Fielding session added for Monday at 4:00 PM',
    time: 'Yesterday',
    icon: <CalendarIcon className="size-5" />,
  },
  {
    title: 'Player updated',
    detail: 'Rhea Kapoor moved to the U14 squad',
    time: '2d ago',
    icon: <PlayersIcon className="size-5" />,
  },
]

const quickActions = [
  {
    label: 'Add player',
    to: '/players',
    icon: <PlayersIcon className="size-5" />,
  },
  {
    label: 'Create match',
    to: '/teams',
    icon: <PerformanceIcon className="size-5" />,
  },
  {
    label: 'Schedule event',
    to: '/calendar',
    icon: <CalendarIcon className="size-5" />,
  },
]

export default function HomePage() {
  return (
    <div className="mx-auto w-full max-w-7xl">
      <header className="flex flex-col gap-6 border-b border-slate-200 pb-8 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <h1
            className="text-3xl font-bold tracking-tight text-slate-900 md:text-4xl"
            tabIndex={-1}
          >
            Good evening, Coach
          </h1>
          <p className="mt-2 max-w-2xl text-base leading-7 text-slate-600 md:text-lg">
            Here’s what’s happening at the academy.
          </p>
        </div>

        <nav aria-label="Quick actions" className="flex flex-wrap gap-3">
          {quickActions.map((action) => (
            <Link
              key={action.label}
              to={action.to}
              className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-academy bg-white px-4 py-2 text-sm font-semibold text-slate-900 transition-colors hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
            >
              <span className="text-academy" aria-hidden="true">
                {action.icon}
              </span>
              {action.label}
            </Link>
          ))}
        </nav>
      </header>

      <section aria-label="Academy summary" className="py-8">
        <div className="grid overflow-hidden rounded-xl border border-slate-200 bg-white sm:grid-cols-3 sm:divide-x sm:divide-slate-200">
          <div className="flex min-w-0 gap-4 border-b border-slate-200 p-5 sm:border-b-0 lg:p-6">
            <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-academy text-slate-900" aria-hidden="true">
              <CalendarIcon className="size-6" />
            </span>
            <div className="min-w-0">
              <h2 className="font-semibold text-slate-900">Upcoming training</h2>
              <p className="mt-1 font-semibold text-slate-800">Tomorrow, 5:00 PM</p>
              <p className="mt-1 text-sm text-slate-600">Batting fundamentals · U15</p>
            </div>
          </div>
          <div className="flex min-w-0 gap-4 border-b border-slate-200 p-5 sm:border-b-0 lg:p-6">
            <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-academy text-slate-900" aria-hidden="true">
              <MatchIcon className="size-6" />
            </span>
            <div className="min-w-0">
              <h2 className="font-semibold text-slate-900">Next match</h2>
              <p className="mt-1 font-semibold text-slate-800">Sat, 25 Jul · 10:30 AM</p>
              <p className="mt-1 text-sm text-slate-600">U14 vs Northside CC</p>
            </div>
          </div>
          <div className="flex min-w-0 gap-4 p-5 lg:p-6">
            <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-academy text-slate-900" aria-hidden="true">
              <PlayersIcon className="size-6" />
            </span>
            <div className="min-w-0">
              <h2 className="font-semibold text-slate-900">Active players</h2>
              <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900">84</p>
              <p className="mt-1 text-sm text-slate-600">Across 6 teams</p>
            </div>
          </div>
        </div>
      </section>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1.55fr)_minmax(18rem,0.8fr)]">
        <section aria-labelledby="upcoming-events-heading" className="min-w-0">
          <div className="flex items-center justify-between gap-4">
            <h2 id="upcoming-events-heading" className="text-xl font-bold text-slate-900">
              Upcoming events
            </h2>
            <Link
              to="/calendar"
              className="rounded-md px-2 py-1 text-sm font-semibold text-slate-700 underline decoration-academy decoration-2 underline-offset-4 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
            >
              View calendar
            </Link>
          </div>

          <ul className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white">
            {upcomingEvents.map((event) => (
              <li
                key={`${event.month}-${event.day}-${event.title}`}
                className="grid gap-4 border-b border-slate-200 p-5 last:border-b-0 sm:grid-cols-[4.25rem_minmax(0,1fr)_auto] sm:items-center"
              >
                <time className="flex items-baseline gap-2 sm:block sm:text-center" dateTime={`2026-07-${event.day}`}>
                  <span className="text-xs font-bold text-slate-600 sm:block">{event.month}</span>
                  <span className="text-2xl font-bold tabular-nums text-slate-900 sm:block">{event.day}</span>
                  <span className="text-xs font-semibold text-slate-600 sm:block">{event.weekday}</span>
                </time>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-600">{event.time}</p>
                  <h3 className="mt-1 font-bold text-slate-900">{event.title}</h3>
                  <p className="mt-1 text-sm text-slate-600">
                    {event.location} · {event.attendance}
                  </p>
                </div>
                <span className="w-fit rounded-md border border-academy px-2.5 py-1 text-xs font-semibold text-slate-800">
                  {event.category}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="recent-activity-heading" className="min-w-0 lg:border-l lg:border-slate-200 lg:pl-8">
          <h2 id="recent-activity-heading" className="text-xl font-bold text-slate-900">
            Recent academy activity
          </h2>
          <ol className="ml-5 mt-5 space-y-6 border-l border-slate-200 pl-5">
            {recentActivity.map((activity) => (
              <li key={`${activity.title}-${activity.detail}`} className="relative flex min-w-0 gap-3">
                <span className="absolute -left-[2.35rem] flex size-9 items-center justify-center rounded-full bg-academy text-slate-900 ring-4 ring-slate-50" aria-hidden="true">
                  {activity.icon}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                    <h3 className="font-semibold text-slate-900">{activity.title}</h3>
                    <span className="text-xs font-medium text-slate-500">{activity.time}</span>
                  </div>
                  <p className="mt-1 text-sm leading-6 text-slate-600">{activity.detail}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  )
}
