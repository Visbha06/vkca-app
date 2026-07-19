import { useSidebar } from '../layouts/SidebarContext'

export default function MobileNavToggle() {
  const { mobileOpen, openMobile } = useSidebar()

  return (
    <button
      id="mobile-navigation-toggle"
      type="button"
      aria-controls="application-sidebar"
      aria-expanded={mobileOpen}
      aria-label="Open navigation menu"
      className="inline-flex size-11 items-center justify-center rounded-lg text-academy transition-colors hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 md:hidden"
      onClick={openMobile}
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
        <path d="M4 7h16M4 12h16M4 17h16" />
      </svg>
    </button>
  )
}
