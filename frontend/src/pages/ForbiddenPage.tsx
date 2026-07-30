import { Link } from 'react-router'

export default function ForbiddenPage() {
  return (
    <section className="mx-auto max-w-2xl py-12">
      <p className="text-sm font-semibold uppercase tracking-wide text-slate-600">
        403 Forbidden
      </p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
        Coaches Portal is for coaches only.
      </h1>
      <p className="mt-4 max-w-prose text-base leading-7 text-slate-600">
        Your account does not have access to coach records or academy management
        tools.
      </p>
      <Link
        className="mt-6 inline-flex min-h-11 items-center justify-center rounded-lg border border-academy bg-white px-4 text-sm font-semibold text-slate-900 transition-colors hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
        to="/"
      >
        Return to Dashboard
      </Link>
    </section>
  )
}
