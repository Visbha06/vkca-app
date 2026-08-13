import { useEffect, useRef, type RefObject } from 'react'

const pageTitles: Record<string, string> = {
  '/': 'Home',
  '/players': 'Player Directory',
  '/teams': 'Teams',
  '/coaches': 'Coaches Portal',
  '/calendar': 'Calendar',
  '/audit-log': 'Audit Log',
  '/settings': 'User Settings',
  '/data-quality': 'Data Quality'
}

const mobileViewportQuery = '(max-width: 47.999rem)'

function getPageTitle(pathname: string) {
  const normalizedPath = pathname === '/' ? pathname : pathname.replace(/\/+$/, '')
  return pageTitles[normalizedPath] ?? 'Page Not Found'
}

export function useAppLayoutEffects(
  pathname: string,
  sidebarRef: RefObject<HTMLElement | null>,
  mobileOpen: boolean,
  closeMobile: () => void,
) {
  const previousFocusRef = useRef<HTMLElement | null>(null)
  const previousPathRef = useRef<string | null>(null)

  useEffect(() => {
    document.title = `${getPageTitle(pathname)} | VK Cricket Academy`
    const previousPath = previousPathRef.current
    if (previousPath !== null && previousPath !== pathname) {
      let headingObserver: MutationObserver | null = null
      const focusTimer = window.setTimeout(() => {
        const settingsTrigger = document.querySelector<HTMLElement>('a[aria-label="User Settings"]')
        if (previousPath !== '/settings' || document.activeElement !== settingsTrigger) {
          const focusHeading = () => {
            const heading = document.querySelector<HTMLElement>('#main-content h1')
            if (heading === null) return false
            heading.focus()
            return true
          }

          if (!focusHeading()) {
            const mainContent = document.querySelector<HTMLElement>('#main-content')
            if (mainContent !== null) {
              headingObserver = new MutationObserver(() => {
                if (focusHeading()) headingObserver?.disconnect()
              })
              headingObserver.observe(mainContent, { childList: true, subtree: true })
            }
          }
        }
      }, 0)
      previousPathRef.current = pathname
      return () => {
        window.clearTimeout(focusTimer)
        headingObserver?.disconnect()
      }
    }
    previousPathRef.current = pathname
  }, [pathname])

  useEffect(() => {
    if (!mobileOpen) return
    const mobileMedia = window.matchMedia?.(mobileViewportQuery)
    if (mobileMedia && !mobileMedia.matches) {
      closeMobile()
      return
    }
    const previousBodyOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const activeElement = document.activeElement as HTMLElement | null
    previousFocusRef.current = activeElement && activeElement !== document.body
      ? activeElement
      : document.querySelector<HTMLElement>('#mobile-navigation-toggle')
    const focusableElements = Array.from(
      sidebarRef.current?.querySelectorAll<HTMLElement>('[data-mobile-drawer-focus]') ?? [],
    )
    focusableElements[0]?.focus()

    function handleDrawerKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        closeMobile()
      } else if (event.key === 'Tab' && focusableElements.length > 0) {
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
    }

    document.addEventListener('keydown', handleDrawerKeyDown)
    return () => {
      document.removeEventListener('keydown', handleDrawerKeyDown)
      document.body.style.overflow = previousBodyOverflow
      const stillMobile = window.matchMedia?.(mobileViewportQuery).matches ?? true
      if (stillMobile && previousFocusRef.current?.isConnected) previousFocusRef.current.focus()
    }
  }, [closeMobile, mobileOpen, sidebarRef])

  useEffect(() => {
    const mobileMedia = window.matchMedia?.(mobileViewportQuery)
    if (!mobileMedia) return
    const closeAtDesktop = (event: MediaQueryListEvent) => {
      if (!event.matches) {
        sidebarRef.current?.querySelector<HTMLElement>('a[aria-current="page"]')?.focus()
        closeMobile()
      }
    }
    mobileMedia.addEventListener('change', closeAtDesktop)
    return () => mobileMedia.removeEventListener('change', closeAtDesktop)
  }, [closeMobile, sidebarRef])
}
