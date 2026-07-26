import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useSidebar } from '../SidebarContext'

interface SidebarNavLinkProps {
  to: string
  label: string
  icon: ReactNode
  iconOnly?: boolean
  state?: { from: string }
}

export default function SidebarNavLink({
  to,
  label,
  icon,
  iconOnly = false,
  state,
}: SidebarNavLinkProps) {
  const { closeMobile, expanded } = useSidebar()

  return (
    <NavLink
      aria-label={label}
      className={({ isActive }) =>
        `flex min-h-11 items-center rounded-lg px-3 py-2 font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 focus:ring-offset-slate-900 ${
          iconOnly
            ? 'size-11 justify-center p-0'
            : expanded
              ? 'gap-3'
              : 'gap-3 md:justify-center md:gap-0 md:px-0'
        } ${
          isActive
            ? 'bg-white text-slate-900 ring-2 ring-inset ring-academy'
            : 'text-white hover:bg-white/15'
        }`
      }
      data-mobile-drawer-focus
      end={to === '/'}
      onClick={closeMobile}
      title={iconOnly || !expanded ? label : undefined}
      state={state}
      to={to}
    >
      <span className="size-6 shrink-0" aria-hidden="true">
        {icon}
      </span>
      {!iconOnly && (
        <span className={`truncate ${expanded ? '' : 'md:hidden'}`}>{label}</span>
      )}
    </NavLink>
  )
}
