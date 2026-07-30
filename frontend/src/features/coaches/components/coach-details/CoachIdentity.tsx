import type { ReactNode } from 'react'
import type { CoachResponse } from '../../types/coach'

interface CoachIdentityProps {
  coach: CoachResponse
  trailing?: ReactNode
}

function initials(firstName: string, lastName: string) {
  return `${firstName.trim()[0] ?? ''}${lastName.trim()[0] ?? ''}`.toUpperCase() || '-'
}

export default function CoachIdentity({ coach, trailing }: CoachIdentityProps) {
  const fullName = `${coach.first_name} ${coach.last_name}`.trim()
  const avatarClass =
    coach.role === 'head coach'
      ? 'bg-rose-100 text-rose-950'
      : 'bg-sky-100 text-sky-950'

  return (
    <span className="flex min-w-0 items-center gap-3">
      <span aria-hidden="true" className={`flex size-11 shrink-0 items-center justify-center rounded-full text-sm font-bold ${avatarClass}`}>
        {initials(coach.first_name, coach.last_name)}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-semibold text-slate-900">{fullName}</span>
        <span className="mt-0.5 block text-sm text-slate-600">{coach.email}</span>
      </span>
      {trailing}
    </span>
  )
}
