import { useEffect, useRef } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import MobileNavCloseButton from '../components/MobileNavCloseButton'
import MobileNavToggle from '../components/MobileNavToggle'
import LogoutButton from '../components/LogoutButton'
import SidebarBrand from '../components/SidebarBrand'
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
]

const pageTitles: Record<string, string> = {
  '/': 'Home',
  '/players': 'Player Directory',
  '/teams': 'Teams',
  '/coaches': 'Coaches Portal',
  '/calendar': 'Calendar',
  '/settings': 'User Settings',
}

const mobileViewportQuery = '(max-width: 47.999rem)'

function getPageTitle(pathname: string) {
  const normalizedPath =
    pathname === '/' ? pathname : pathname.replace(/\/+$/, '')
  return pageTitles[normalizedPath] ?? 'Page Not Found'
}

function AppLayoutShell() {
  const { closeMobile, expanded, mobileOpen } = useSidebar()
  const { pathname } = useLocation()
  const sidebarRef = useRef<HTMLElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)
  const previousPathRef = useRef<string | null>(null)

  useEffect(() => {
    const pageTitle = getPageTitle(pathname)
    document.title = `${pageTitle} | VK Cricket Academy`

    if (previousPathRef.current !== null && previousPathRef.current !== pathname) {
      const focusTimer = window.setTimeout(() => {
        document.querySelector<HTMLElement>('#main-content h1')?.focus()
      }, 0)

      previousPathRef.current = pathname
      return () => window.clearTimeout(focusTimer)
    }

    previousPathRef.current = pathname
  }, [pathname])

  useEffect(() => {
    if (!mobileOpen) {
      return
    }

    const mobileMedia = window.matchMedia?.(mobileViewportQuery)
    if (mobileMedia && !mobileMedia.matches) {
      closeMobile()
      return
    }

    const previousBodyOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const activeElement = document.activeElement as HTMLElement | null
    previousFocusRef.current =
      activeElement && activeElement !== document.body
        ? activeElement
        : document.querySelector<HTMLElement>('#mobile-navigation-toggle')
    const sidebar = sidebarRef.current
    const focusableElements = Array.from(
      sidebar?.querySelectorAll<HTMLElement>('[data-mobile-drawer-focus]') ?? [],
    )
    focusableElements[0]?.focus()

    function handleDrawerKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        closeMobile()
        return
      }

      if (event.key !== 'Tab' || focusableElements.length === 0) {
        return
      }

      const firstElement = focusableElements[0]
      const lastElement = focusableElements[focusableElements.length - 1]

      if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault()
        lastElement.focus()
      } else if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault()
        firstElement.focus()
      }
    }

    document.addEventListener('keydown', handleDrawerKeyDown)
    return () => {
      document.removeEventListener('keydown', handleDrawerKeyDown)
      document.body.style.overflow = previousBodyOverflow
      const stillMobile = window.matchMedia?.(mobileViewportQuery).matches ?? true
      if (stillMobile && previousFocusRef.current?.isConnected) {
        previousFocusRef.current.focus()
      }
    }
  }, [closeMobile, mobileOpen])

  useEffect(() => {
    const mobileMedia = window.matchMedia?.(mobileViewportQuery)
    if (!mobileMedia) {
      return
    }

    const closeAtDesktop = (event: MediaQueryListEvent) => {
      if (!event.matches) {
        sidebarRef.current
          ?.querySelector<HTMLElement>('a[aria-current="page"]')
          ?.focus()
        closeMobile()
      }
    }

    mobileMedia.addEventListener('change', closeAtDesktop)
    return () => mobileMedia.removeEventListener('change', closeAtDesktop)
  }, [closeMobile])

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
          {navigationItems.map((item) => (
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
