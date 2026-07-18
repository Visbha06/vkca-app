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
  const { expanded } = useSidebar()

  return (
    <NavLink
      aria-label={label}
      className={({ isActive }) =>
        `flex items-center rounded-lg px-3 py-2 font-medium transition-colors ${
          expanded ? 'gap-3' : 'justify-center'
        } ${
          isActive
            ? 'bg-white text-academy shadow-sm'
            : 'text-white hover:bg-white/15'
        }`
      }
      end={to === '/'}
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
