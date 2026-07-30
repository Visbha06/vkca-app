interface CoachStatusIndicatorProps {
  isActive: boolean
}

export default function CoachStatusIndicator({
  isActive,
}: CoachStatusIndicatorProps) {
  const label = isActive ? 'Active' : 'Inactive'

  return (
    <span
      aria-label={`Status: ${label}`}
      className={`inline-flex min-h-6 shrink-0 items-center gap-1.5 text-xs font-semibold ${
        isActive ? 'text-emerald-800' : 'text-slate-600'
      }`}
    >
      <span
        aria-hidden="true"
        className={`size-2 shrink-0 rounded-full ${
          isActive ? 'bg-emerald-600' : 'bg-red-500'
        }`}
      />
      <span>{label}</span>
    </span>
  )
}
