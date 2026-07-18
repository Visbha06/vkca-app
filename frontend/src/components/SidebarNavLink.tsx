import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useSidebar } from '../layouts/SidebarContext'

interface SidebarNavLinkProps {
  to: string
  label: string
  icon: ReactNode
}

export default function SidebarNavLink({
  to,
  label,
  icon,
}: SidebarNavLinkProps) {
  const { closeMobile, expanded } = useSidebar()

  return (
    <NavLink
      aria-label={label}
      className={({ isActive }) =>
        `flex items-center rounded-lg px-3 py-2 font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 focus:ring-offset-slate-900 ${
          expanded ? 'gap-3' : 'justify-center'
        } ${
          isActive
            ? 'bg-white text-slate-900 shadow-sm ring-2 ring-inset ring-academy'
            : 'text-white hover:bg-white/15'
        }`
      }
      end={to === '/'}
      onClick={closeMobile}
      title={expanded ? undefined : label}
      to={to}
    >
      <span className="size-6 shrink-0" aria-hidden="true">
        {icon}
      </span>
      {expanded && <span className="truncate">{label}</span>}
    </NavLink>
  )
}
