import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

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
  return (
    <NavLink
      className={({ isActive }) =>
        `flex items-center gap-3 rounded-lg px-3 py-2 font-medium transition-colors ${
          isActive
            ? 'bg-white text-academy shadow-sm'
            : 'text-white hover:bg-white/15'
        }`
      }
      end={to === '/'}
      to={to}
    >
      <span className="size-6 shrink-0" aria-hidden="true">
        {icon}
      </span>
      <span>{label}</span>
    </NavLink>
  )
}
