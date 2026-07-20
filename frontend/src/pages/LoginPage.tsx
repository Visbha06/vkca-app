import { useRef, useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { DesktopLoginBrand, MobileLoginBrand } from '../components/LoginBrand'
import LoginSubmitContent from '../components/LoginSubmitContent'
import PasswordVisibilityIcon from '../components/PasswordVisibilityIcon'
import {
  getLoginErrorMessage,
  getRedirectTarget,
  validateCredentials,
  type FieldErrors,
} from './loginPageUtils'

export default function LoginPage() {
  const { isLoginPending, login } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordVisible, setPasswordVisible] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [submitError, setSubmitError] = useState<string | null>(null)
  const emailInputRef = useRef<HTMLInputElement>(null)
  const passwordInputRef = useRef<HTMLInputElement>(null)
  const reason = searchParams.get('reason')
  const accountNotice =
    reason === 'session-expired'
      ? {
          message: 'Your session has expired. Please sign in again.',
          className: 'border-amber-200 bg-amber-50 text-amber-900',
        }
      : reason === 'password-changed'
        ? {
            message: 'Your password was changed. Please sign in again.',
            className: 'border-emerald-200 bg-emerald-50 text-emerald-900',
          }
        : null

  function handleCredentialChange(field: keyof FieldErrors, value: string) {
    if (field === 'email') setEmail(value)
    else setPassword(value)

    setFieldErrors((currentErrors) => {
      if (!currentErrors[field]) return currentErrors
      return field === 'email'
        ? { password: currentErrors.password }
        : { email: currentErrors.email }
    })
    setSubmitError(null)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const normalizedEmail = email.trim()
    const errors = validateCredentials(normalizedEmail, password)

    setFieldErrors(errors)
    setSubmitError(null)
    const firstInvalidInput = errors.email
      ? emailInputRef.current
      : errors.password
        ? passwordInputRef.current
        : null
    if (firstInvalidInput) {
      firstInvalidInput.focus()
      return
    }
    if (isLoginPending) return

    try {
      await login(normalizedEmail, password)
      navigate(getRedirectTarget(searchParams.get('redirect')), { replace: true })
    } catch (error) {
      setSubmitError(getLoginErrorMessage(error))
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4 sm:p-6 lg:p-8">
      <section className="grid w-full max-w-5xl overflow-hidden rounded-xl border border-slate-200 bg-white lg:grid-cols-2">
        <DesktopLoginBrand />

        <div className="flex items-center p-6 sm:p-10 lg:p-12">
          <div className="mx-auto w-full max-w-sm">
            <MobileLoginBrand />

            <header>
              <h1 className="text-3xl font-bold tracking-tight text-slate-900">
                Sign in to your account
              </h1>
              <p className="mt-2 leading-6 text-slate-600">
                Use your academy credentials to continue.
              </p>
            </header>

            {accountNotice && (
              <p
                className={`mt-6 rounded-lg border p-3 text-sm font-medium ${accountNotice.className}`}
                role="status"
              >
                {accountNotice.message}
              </p>
            )}

            <form className="mt-8 space-y-5" noValidate onSubmit={handleSubmit}>
              <div>
                <label className="text-sm font-semibold text-slate-800" htmlFor="login-email">
                  Email address
                </label>
                <input
                  ref={emailInputRef}
                  id="login-email"
                  type="email"
                  autoComplete="email"
                  aria-describedby={fieldErrors.email ? 'login-email-error' : undefined}
                  aria-invalid={fieldErrors.email ? 'true' : undefined}
                  className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-base text-slate-900 outline-none transition-colors placeholder:text-slate-500 focus:border-academy focus:ring-2 focus:ring-academy/40"
                  disabled={isLoginPending}
                  value={email}
                  onChange={(event) => handleCredentialChange('email', event.target.value)}
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
                    ref={passwordInputRef}
                    id="login-password"
                    type={passwordVisible ? 'text' : 'password'}
                    autoComplete="current-password"
                    aria-describedby={fieldErrors.password ? 'login-password-error' : undefined}
                    aria-invalid={fieldErrors.password ? 'true' : undefined}
                    className="min-h-11 w-full rounded-lg border border-slate-300 bg-white py-2 pl-3 pr-12 text-base text-slate-900 outline-none transition-colors focus:border-academy focus:ring-2 focus:ring-academy/40"
                    disabled={isLoginPending}
                    value={password}
                    onChange={(event) => handleCredentialChange('password', event.target.value)}
                  />
                  <button
                    type="button"
                    aria-label={passwordVisible ? 'Hide password' : 'Show password'}
                    className="absolute inset-y-0 right-0 flex min-w-11 items-center justify-center rounded-r-lg text-slate-600 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-academy disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={isLoginPending}
                    onClick={() => setPasswordVisible((visible) => !visible)}
                  >
                    <PasswordVisibilityIcon visible={passwordVisible} />
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
                <LoginSubmitContent pending={isLoginPending} />
              </button>
            </form>
          </div>
        </div>
      </section>
    </main>
  )
}
