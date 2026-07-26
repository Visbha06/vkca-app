interface EmptyStateAction {
  label: string
  onClick: () => void
  variant?: 'primary' | 'secondary'
}

interface EmptyStateProps {
  title: string
  description: string
  action?: EmptyStateAction
}

export default function EmptyState({
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-5 py-12 text-center sm:px-6">
      <p className="font-semibold text-slate-900">{title}</p>
      <p className="mx-auto mt-2 max-w-prose text-sm leading-6 text-slate-600">
        {description}
      </p>
      {action !== undefined ? (
        <button
          type="button"
          className={`mt-5 inline-flex min-h-11 items-center justify-center rounded-lg px-4 text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 ${
            action.variant === 'secondary'
              ? 'border border-academy bg-white text-slate-900 hover:bg-academy/10'
              : 'bg-slate-900 text-white hover:bg-slate-800'
          }`}
          onClick={action.onClick}
        >
          {action.label}
        </button>
      ) : null}
    </div>
  )
}
