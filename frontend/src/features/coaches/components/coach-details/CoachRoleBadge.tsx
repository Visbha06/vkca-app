import type { CoachResponse } from '../../types/coach'

export default function CoachRoleBadge({ role }: Pick<CoachResponse, 'role'>) {
  const label = role === 'head coach' ? 'Head Coach' : 'Assistant Coach'
  return (
    <span className="inline-flex min-h-6 items-center rounded-md border border-academy bg-academy/10 px-2 text-xs font-semibold text-slate-800">
      {label}
    </span>
  )
}
