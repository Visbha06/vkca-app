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
      className="mt-3 flex w-full items-center justify-center rounded-lg p-2 text-white transition-colors hover:bg-white/15 focus:outline-none focus:ring-2 focus:ring-white"
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
