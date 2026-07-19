import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ApiClientError } from '../api/client'
import academyLogo from '../assets/placeholderLogo.png'
import { useAuth } from '../auth/AuthContext'

interface FieldErrors {
  email?: string
  password?: string
}

function getRedirectTarget(redirect: string | null) {
  return redirect?.startsWith('/') && !redirect.startsWith('//') ? redirect : '/'
}

function getLoginErrorMessage(error: unknown) {
  if (error instanceof ApiClientError) {
    if (error.status === 429) {
      return 'Too many sign-in attempts. Please wait and try again.'
    }

    if (error.status === 401 || error.status === 403) {
      return 'Invalid email or password.'
    }
  }

  return 'Unable to sign in right now. Please try again.'
}

function VisibilityIcon({ visible }: { visible: boolean }) {
  if (visible) {
    return (
      <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 24 24">
        <path
          d="m3 3 18 18M10.6 10.7a2 2 0 0 0 2.7 2.7M9.9 4.2A10.8 10.8 0 0 1 12 4c5.5 0 9 5 9 5a17 17 0 0 1-2.1 2.5M6.6 6.6C4.3 8.1 3 10 3 10s3.5 5 9 5c1.2 0 2.3-.2 3.3-.6"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2"
        />
      </svg>
    )
  }

  return (
    <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 24 24">
      <path
        d="M3 12s3.5-5 9-5 9 5 9 5-3.5 5-9 5-9-5-9-5Z"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="2"
      />
      <circle cx="12" cy="12" r="2" stroke="currentColor" strokeWidth="2" />
    </svg>
  )
}

export default function LoginPage() {
  const { isLoginPending, login } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordVisible, setPasswordVisible] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [submitError, setSubmitError] = useState<string | null>(null)
  const sessionExpired = searchParams.get('reason') === 'session-expired'

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const errors: FieldErrors = {}
    if (email.trim() === '') errors.email = 'Email is required.'
    if (password === '') errors.password = 'Password is required.'

    setFieldErrors(errors)
    setSubmitError(null)
    if (Object.keys(errors).length > 0 || isLoginPending) return

    try {
      await login(email.trim(), password)
      navigate(getRedirectTarget(searchParams.get('redirect')), { replace: true })
    } catch (error) {
      setSubmitError(getLoginErrorMessage(error))
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4 sm:p-6 lg:p-8">
      <section className="grid w-full max-w-5xl overflow-hidden rounded-xl border border-slate-200 bg-white lg:grid-cols-2">
        <div className="hidden bg-slate-900 p-12 text-white ring-2 ring-inset ring-academy lg:flex lg:flex-col lg:justify-between">
          <div className="flex items-center gap-4">
            <img
              src={academyLogo}
              alt=""
              aria-hidden="true"
              className="size-16 rounded-lg bg-white object-cover"
            />
            <div>
              <p className="text-xl font-bold">VK Cricket Academy</p>
              <p className="mt-1 text-sm text-slate-300">Academy Portal</p>
            </div>
          </div>
          <div className="max-w-sm">
            <h2 className="text-3xl font-bold tracking-tight text-white">
              Keep the academy moving.
            </h2>
            <p className="mt-4 leading-7 text-slate-300">
              Organize teams, support player development, and stay ready for the next session.
            </p>
          </div>
        </div>

        <div className="flex items-center p-6 sm:p-10 lg:p-12">
          <div className="mx-auto w-full max-w-sm">
            <div className="mb-8 flex items-center gap-3 lg:hidden">
              <img
                src={academyLogo}
                alt=""
                aria-hidden="true"
                className="size-12 rounded-lg bg-white object-cover"
              />
              <div>
                <p className="font-bold text-slate-900">VK Cricket Academy</p>
                <p className="text-sm text-slate-600">Academy Portal</p>
              </div>
            </div>

            <header>
              <h1 className="text-3xl font-bold tracking-tight text-slate-900">
                Sign in to your account
              </h1>
              <p className="mt-2 leading-6 text-slate-600">
                Use your academy credentials to continue.
              </p>
            </header>

            {sessionExpired && (
              <p
                className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm font-medium text-amber-900"
                role="status"
              >
                Your session has expired. Please sign in again.
              </p>
            )}

            <form className="mt-8 space-y-5" noValidate onSubmit={handleSubmit}>
              <div>
                <label className="text-sm font-semibold text-slate-800" htmlFor="login-email">
                  Email address
                </label>
                <input
                  id="login-email"
                  type="email"
                  autoComplete="email"
                  autoFocus
                  aria-describedby={fieldErrors.email ? 'login-email-error' : undefined}
                  aria-invalid={fieldErrors.email ? 'true' : undefined}
                  className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-base text-slate-900 outline-none transition-colors placeholder:text-slate-500 focus:border-academy focus:ring-2 focus:ring-academy/40"
                  disabled={isLoginPending}
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
                {fieldErrors.email && (
                  <p id="login-email-error" className="mt-2 text-sm font-medium text-red-700">
                    {fieldErrors.email}
                  </p>
                )}
              </div>

              <div>
                <label className="text-sm font-semibold text-slate-800" htmlFor="login-password">
                  Password
                </label>
                <div className="relative mt-2">
                  <input
                    id="login-password"
                    type={passwordVisible ? 'text' : 'password'}
                    autoComplete="current-password"
                    aria-describedby={fieldErrors.password ? 'login-password-error' : undefined}
                    aria-invalid={fieldErrors.password ? 'true' : undefined}
                    className="min-h-11 w-full rounded-lg border border-slate-300 bg-white py-2 pl-3 pr-12 text-base text-slate-900 outline-none transition-colors focus:border-academy focus:ring-2 focus:ring-academy/40"
                    disabled={isLoginPending}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                  />
                  <button
                    type="button"
                    aria-label={passwordVisible ? 'Hide password' : 'Show password'}
                    className="absolute inset-y-0 right-0 flex min-w-11 items-center justify-center rounded-r-lg text-slate-600 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-academy disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={isLoginPending}
                    onClick={() => setPasswordVisible((visible) => !visible)}
                  >
                    <VisibilityIcon visible={passwordVisible} />
                  </button>
                </div>
                {fieldErrors.password && (
                  <p id="login-password-error" className="mt-2 text-sm font-medium text-red-700">
                    {fieldErrors.password}
                  </p>
                )}
              </div>

              {submitError && (
                <p className="rounded-lg bg-red-50 p-3 text-sm font-medium text-red-800" role="alert">
                  {submitError}
                </p>
              )}

              <button
                type="submit"
                aria-busy={isLoginPending}
                aria-label={isLoginPending ? 'Logging in' : undefined}
                className="flex min-h-11 w-full items-center justify-center rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-500"
                disabled={isLoginPending}
              >
                {isLoginPending ? (
                  <>
                    <svg
                      aria-hidden="true"
                      className="mr-2 size-4 animate-spin"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="9"
                        stroke="currentColor"
                        strokeWidth="3"
                      />
                      <path
                        className="opacity-75"
                        d="M21 12a9 9 0 0 0-9-9"
                        stroke="currentColor"
                        strokeLinecap="round"
                        strokeWidth="3"
                      />
                    </svg>
                    Logging in
                    <span className="sr-only" role="status">
                      Signing in…
                    </span>
                  </>
                ) : (
                  'Log in'
                )}
              </button>
            </form>
          </div>
        </div>
      </section>
    </main>
  )
}
