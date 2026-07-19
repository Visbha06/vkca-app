import { useSidebar } from '../layouts/SidebarContext'

export default function MobileNavCloseButton() {
  const { closeMobile } = useSidebar()

  return (
    <button
      type="button"
      aria-controls="application-sidebar"
      aria-expanded="true"
      aria-label="Close navigation menu"
      className="inline-flex size-11 shrink-0 items-center justify-center rounded-lg text-white transition-colors hover:bg-white/15 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 focus:ring-offset-slate-900 md:hidden"
      data-mobile-drawer-focus
      onClick={closeMobile}
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
        <path d="m6 6 12 12M18 6 6 18" />
      </svg>
    </button>
  )
}
