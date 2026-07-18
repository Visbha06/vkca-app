import { useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import MobileNavToggle from '../components/MobileNavToggle'
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
  const { closeMobile, expanded, mobileOpen } = useSidebar()

  useEffect(() => {
    if (!mobileOpen) {
      return
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        closeMobile()
      }
    }

    document.addEventListener('keydown', closeOnEscape)
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [closeMobile, mobileOpen])

  return (
    <div className="min-h-screen overflow-x-hidden bg-white text-slate-900">
      <aside
        id="application-sidebar"
        aria-label="Application sidebar"
        className={`app-sidebar fixed inset-y-0 left-0 z-40 flex flex-col overflow-hidden bg-slate-900 p-3 transition-[transform,width] duration-200 ${
          expanded ? 'w-sidebar-expanded' : 'w-sidebar-collapsed'
        }`}
        data-mobile-open={mobileOpen}
      >
        <nav aria-label="Primary navigation" className="flex-1 space-y-1">
          {navigationItems.map((item) => (
            <SidebarNavLink key={item.to} {...item} />
          ))}
        </nav>
        <SidebarToggle />
      </aside>
      <button
        type="button"
        aria-hidden="true"
        className="mobile-navigation-backdrop"
        data-open={mobileOpen}
        data-testid="mobile-navigation-backdrop"
        tabIndex={-1}
        onClick={closeMobile}
      />
      <main
        className={`app-main min-h-screen min-w-0 bg-slate-50 transition-[margin] duration-200 ${
          expanded ? 'md:ml-sidebar-expanded' : 'md:ml-sidebar-collapsed'
        }`}
      >
        <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 md:hidden">
          <MobileNavToggle />
          <span className="font-semibold text-slate-800">VK Cricket Academy</span>
        </header>
        <div className="p-4 md:p-6">
          <Outlet />
        </div>
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
