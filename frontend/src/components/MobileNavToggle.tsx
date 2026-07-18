import { useSidebar } from '../layouts/SidebarContext'

export default function MobileNavToggle() {
  const { mobileOpen, openMobile, closeMobile } = useSidebar()

  return (
    <button
      type="button"
      aria-controls="application-sidebar"
      aria-expanded={mobileOpen}
      aria-label={mobileOpen ? 'Close navigation menu' : 'Open navigation menu'}
      className="inline-flex size-11 items-center justify-center rounded-lg text-academy transition-colors hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 md:hidden"
      onClick={mobileOpen ? closeMobile : openMobile}
    >
      <svg
        aria-hidden="true"
        className="size-6"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
        viewBox="0 0 24 24"
      >
        {mobileOpen ? (
          <path d="m6 6 12 12M18 6 6 18" />
        ) : (
          <path d="M4 7h16M4 12h16M4 17h16" />
        )}
      </svg>
    </button>
  )
}
