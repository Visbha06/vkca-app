import { useRef } from 'react'
import { Outlet, useLocation } from 'react-router'
import LogoutButton from '@features/auth/components/LogoutButton'
import { useAuth } from '@features/auth'
import {
  AuditLogIcon,
  CalendarIcon,
  CoachesIcon,
  HomeIcon,
  PlayersIcon,
  SettingsIcon,
  TeamsIcon,
} from '@shared/components/icons/NavIcons'
import MobileNavCloseButton from './components/MobileNavCloseButton'
import MobileNavToggle from './components/MobileNavToggle'
import SidebarBrand from './components/SidebarBrand'
import SidebarNavLink from './components/SidebarNavLink'
import SidebarToggle from './components/SidebarToggle'
import { SidebarProvider, useSidebar } from './SidebarContext'
import { useAppLayoutEffects } from './useAppLayoutEffects'

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
    to: '/audit-log',
    label: 'Audit Log',
    icon: <AuditLogIcon className="size-6" />,
    headCoachOnly: true,
  },
]

function AppLayoutShell() {
  const { user } = useAuth()
  const { closeMobile, expanded, mobileOpen } = useSidebar()
  const { pathname } = useLocation()
  const sidebarRef = useRef<HTMLElement>(null)
  useAppLayoutEffects(pathname, sidebarRef, mobileOpen, closeMobile)

  return (
    <div className="min-h-screen overflow-x-hidden bg-white text-slate-900">
      <a
        aria-hidden={mobileOpen || undefined}
        className="skip-link"
        href="#main-content"
        tabIndex={mobileOpen ? -1 : undefined}
      >
        Skip to main content
      </a>
      <aside
        ref={sidebarRef}
        id="application-sidebar"
        aria-label="Application sidebar"
        aria-modal={mobileOpen ? 'true' : undefined}
        role={mobileOpen ? 'dialog' : undefined}
        className={`app-sidebar fixed inset-y-0 left-0 z-40 flex w-sidebar-expanded flex-col overflow-x-hidden overflow-y-auto bg-slate-900 p-4 transition-[transform,width,padding] duration-200 ${
          expanded
            ? 'md:w-sidebar-expanded md:p-4'
            : 'md:w-sidebar-collapsed md:p-2.5'
        }`}
        data-mobile-open={mobileOpen}
      >
        <div
          className={`mb-6 flex min-w-0 items-center justify-between gap-3 pt-1 ${
            expanded ? 'px-1' : 'px-1 md:px-0'
          }`}
        >
          <SidebarBrand />
          <MobileNavCloseButton />
        </div>
        <nav aria-label="Primary navigation" className="flex-1 space-y-1">
          {navigationItems
            .filter((item) => {
              if (item.to === '/coaches' && user?.role === 'player') return false
              return !item.headCoachOnly || user?.role === 'head coach'
            })
            .map((item) => (
            <SidebarNavLink key={item.to} {...item} />
            ))}
        </nav>
        <div
          className={`mt-4 flex gap-2 border-t border-white/20 pt-3 ${
            expanded
              ? 'flex-row items-center justify-between'
              : 'flex-row items-center justify-between md:flex-col md:justify-start'
          }`}
          data-testid="sidebar-footer-controls"
        >
          <SidebarNavLink
            to="/settings"
            label="User Settings"
            icon={<SettingsIcon className="size-6" />}
            iconOnly
            state={pathname === '/settings' ? undefined : { from: pathname }}
          />
          <LogoutButton />
          <SidebarToggle />
        </div>
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
        id="main-content"
        aria-hidden={mobileOpen || undefined}
        className={`app-main min-h-screen min-w-0 bg-slate-50 transition-[margin] duration-200 focus:outline-none ${
          expanded ? 'md:ml-sidebar-expanded' : 'md:ml-sidebar-collapsed'
        }`}
        inert={mobileOpen}
        tabIndex={-1}
      >
        <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 md:hidden">
          <MobileNavToggle />
          <span className="min-w-0 truncate font-semibold text-slate-800">
            VK Cricket Academy
          </span>
        </header>
        <div className="p-4 md:p-6 lg:p-8">
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
