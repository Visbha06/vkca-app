import type { SVGProps } from 'react'

type NavIconProps = SVGProps<SVGSVGElement>

const sharedProps = {
  'aria-hidden': true,
  fill: 'none',
  stroke: 'currentColor',
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  strokeWidth: 1.8,
  viewBox: '0 0 24 24',
} as const

export function HomeIcon(props: NavIconProps) {
  return (
    <svg {...sharedProps} {...props}>
      <path d="m3 11 9-8 9 8" />
      <path d="M5.5 9.5V21h13V9.5M9 21v-6h6v6" />
    </svg>
  )
}

export function PlayersIcon(props: NavIconProps) {
  return (
    <svg {...sharedProps} {...props}>
      <circle cx="9" cy="8" r="3" />
      <path d="M3.5 20a5.5 5.5 0 0 1 11 0M16 4.5a3 3 0 0 1 0 5.8M17 14.5a5.5 5.5 0 0 1 3.5 5.5" />
    </svg>
  )
}

export function TeamsIcon(props: NavIconProps) {
  return (
    <svg {...sharedProps} {...props}>
      <path d="M12 3 4.5 6v5c0 4.6 3 8.7 7.5 10 4.5-1.3 7.5-5.4 7.5-10V6L12 3Z" />
      <path d="M9 11.5 11 14l4-5" />
    </svg>
  )
}

export function CoachesIcon(props: NavIconProps) {
  return (
    <svg {...sharedProps} {...props}>
      <circle cx="12" cy="7" r="3" />
      <path d="M6 21v-3a6 6 0 0 1 12 0v3M9 14.8 12 18l3-3.2" />
    </svg>
  )
}

export function CalendarIcon(props: NavIconProps) {
  return (
    <svg {...sharedProps} {...props}>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M8 3v4M16 3v4M3 10h18M8 14h2M14 14h2M8 18h2" />
    </svg>
  )
}

export function AuditLogIcon(props: NavIconProps) {
  return (
    <svg {...sharedProps} {...props}>
      <rect x="5" y="3" width="14" height="18" rx="2" />
      <path d="M8.5 8h7M8.5 12h7M8.5 16h4" />
    </svg>
  )
}

export function DataQualityIcon(props: NavIconProps) {
  return (
    <svg {...sharedProps} {...props}>
      <path d="M12 3 4.5 6v5c0 4.6 3 8.7 7.5 10 4.5-1.3 7.5-5.4 7.5-10V6L12 3Z" />
      <path d="m8.5 12 2.2 2.2 4.8-5" />
    </svg>
  )
}

export function SettingsIcon(props: NavIconProps) {
  return (
    <svg {...sharedProps} {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
    </svg>
  )
}

export function PerformanceIcon(props: NavIconProps) {
  return (
    <svg {...sharedProps} {...props}>
      <path d="M5 20V11h4v9M10 20V4h4v16M15 20v-6h4v6" />
    </svg>
  )
}

export function MatchIcon(props: NavIconProps) {
  return (
    <svg {...sharedProps} {...props}>
      <path d="M8 4h8v4a4 4 0 0 1-8 0V4Z" />
      <path d="M8 6H5v1a4 4 0 0 0 4 4M16 6h3v1a4 4 0 0 1-4 4M12 12v5M8 21h8M9 17h6" />
    </svg>
  )
}
