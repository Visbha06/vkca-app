import { CalendarIcon, MatchIcon, PlayersIcon } from '@shared/components/icons/NavIcons'

const summaryItems = [
  {
    title: 'Upcoming training',
    primary: 'Tomorrow, 5:00 PM',
    secondary: 'Batting fundamentals · U15',
    icon: <CalendarIcon className="size-6" />,
  },
  {
    title: 'Next match',
    primary: 'Sat, 25 Jul · 10:30 AM',
    secondary: 'U14 vs Northside CC',
    icon: <MatchIcon className="size-6" />,
  },
  {
    title: 'Active players',
    primary: '84',
    secondary: 'Across 6 teams',
    icon: <PlayersIcon className="size-6" />,
  },
]

export default function HomeSummary() {
  return (
    <section aria-label="Academy summary" className="py-8">
      <div className="grid overflow-hidden rounded-xl border border-slate-200 bg-white sm:grid-cols-3 sm:divide-x sm:divide-slate-200">
        {summaryItems.map((item, index) => (
          <div
            key={item.title}
            className={`flex min-w-0 gap-4 p-5 lg:p-6 ${index < 2 ? 'border-b border-slate-200 sm:border-b-0' : ''}`}
          >
            <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-academy text-slate-900" aria-hidden="true">
              {item.icon}
            </span>
            <div className="min-w-0">
              <h2 className="font-semibold text-slate-900">{item.title}</h2>
              <p className={`${item.title === 'Active players' ? 'text-2xl font-bold text-slate-900' : 'font-semibold text-slate-800'} mt-1 tabular-nums`}>
                {item.primary}
              </p>
              <p className="mt-1 text-sm text-slate-600">{item.secondary}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
