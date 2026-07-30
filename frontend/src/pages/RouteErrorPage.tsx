import { useEffect } from 'react'
import { isRouteErrorResponse, Link, useRouteError } from 'react-router'

function getErrorMessage(error: unknown) {
  if (isRouteErrorResponse(error)) {
    if (error.status === 404) {
      return 'The requested page could not be found.'
    }

    return `The application could not complete this request (${error.status}).`
  }

  return 'The application encountered an unexpected problem.'
}

export default function RouteErrorPage() {
  const error = useRouteError()

  useEffect(() => {
    document.title = 'Application Error | VK Cricket Academy'
  }, [])

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6 text-slate-900">
      <section aria-labelledby="route-error-title" className="w-full max-w-xl">
        <h1 id="route-error-title" className="text-3xl font-bold text-slate-900">
          We couldn’t open this page
        </h1>
        <p className="mt-4 max-w-prose text-slate-600">{getErrorMessage(error)}</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            className="min-h-11 rounded-lg bg-slate-900 px-4 py-2 font-semibold text-white focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
            onClick={() => window.location.reload()}
          >
            Try again
          </button>
          <Link
            className="inline-flex min-h-11 items-center rounded-lg px-4 py-2 font-semibold text-slate-800 ring-1 ring-inset ring-slate-300 hover:bg-white focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2"
            to="/"
          >
            Return home
          </Link>
        </div>
      </section>
    </main>
  )
}
