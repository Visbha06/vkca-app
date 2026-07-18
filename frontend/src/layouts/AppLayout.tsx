import { Outlet } from 'react-router-dom'
import {
  CalendarIcon,
  CoachesIcon,
  HomeIcon,
  PlayersIcon,
  SettingsIcon,
  TeamsIcon,
} from '../components/NavIcons'
import SidebarNavLink from '../components/SidebarNavLink'
import SidebarToggle from '../components/SidebarToggle'
import { SidebarProvider, useSidebar } from './SidebarContext'

const navigationItems = [
  { to: '/', label: 'Home', icon: <HomeIcon className="size-6" /> },
  {
    to: '/players',
    label: 'Player Directory',
    icon: <PlayersIcon className="size-6" />,
  },
  { to: '/teams', label: 'Teams', icon: <TeamsIcon className="size-6" /> },
  {
    to: '/coaches',
    label: 'Coaches Portal',
    icon: <CoachesIcon className="size-6" />,
  },
  {
    to: '/calendar',
    label: 'Calendar',
    icon: <CalendarIcon className="size-6" />,
  },
  {
    to: '/settings',
    label: 'User Settings',
    icon: <SettingsIcon className="size-6" />,
  },
]

function AppLayoutShell() {
  const { expanded } = useSidebar()

  return (
    <div className="min-h-screen bg-white text-slate-900">
      <aside
        aria-label="Application sidebar"
        className={`fixed inset-y-0 left-0 flex flex-col overflow-hidden bg-academy p-3 transition-[width] duration-200 ${
          expanded ? 'w-sidebar-expanded' : 'w-sidebar-collapsed'
        }`}
      >
        <nav aria-label="Primary navigation" className="flex-1 space-y-1">
          {navigationItems.map((item) => (
            <SidebarNavLink key={item.to} {...item} />
          ))}
        </nav>
        <SidebarToggle />
      </aside>
      <main
        className={`min-h-screen min-w-0 bg-slate-50 p-6 transition-[margin] duration-200 ${
          expanded ? 'ml-sidebar-expanded' : 'ml-sidebar-collapsed'
        }`}
      >
        <Outlet />
      </main>
    </div>
  )
}

export default function AppLayout() {
  return (
    <SidebarProvider>
      <AppLayoutShell />
    </SidebarProvider>
  )
}
