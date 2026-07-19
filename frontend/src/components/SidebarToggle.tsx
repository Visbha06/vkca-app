import type { KeyboardEvent } from 'react'
import { useSidebar } from '../layouts/SidebarContext'

export default function SidebarToggle() {
  const { expanded, toggleExpanded } = useSidebar()

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      toggleExpanded()
    }
  }

  return (
    <button
      type="button"
      aria-expanded={expanded}
      aria-label={expanded ? 'Collapse sidebar' : 'Expand sidebar'}
      className="hidden size-11 shrink-0 items-center justify-center rounded-lg text-white transition-colors hover:bg-white/15 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 focus:ring-offset-slate-900 md:flex"
      onClick={toggleExpanded}
      onKeyDown={handleKeyDown}
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
        <path d={expanded ? 'm15 18-6-6 6-6' : 'm9 18 6-6-6-6'} />
      </svg>
    </button>
  )
}
