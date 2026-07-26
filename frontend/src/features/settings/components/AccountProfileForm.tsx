import { useState, type FormEvent } from 'react'
import { apiClient } from '@shared/api/client'
import {
  useAuth,
  type AuthUser,
  type ProfileUpdateRequest,
} from '@features/auth'

interface ProfileErrors {
  firstName?: string
  lastName?: string
}

interface Feedback {
  kind: 'success' | 'error'
  message: string
}

const inputClassName =
  'mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-base text-slate-900 outline-none transition-colors read-only:cursor-default read-only:bg-slate-100 read-only:text-slate-700 focus:border-academy focus:ring-2 focus:ring-academy/40 disabled:cursor-not-allowed disabled:bg-slate-100'

function formatRole(role: string) {
  return role.charAt(0).toUpperCase() + role.slice(1)
}

export default function AccountProfileForm() {
  const { updateUser, user } = useAuth()
  const [firstName, setFirstName] = useState(user?.first_name ?? '')
  const [lastName, setLastName] = useState(user?.last_name ?? '')
  const [errors, setErrors] = useState<ProfileErrors>({})
  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (user === null) return null

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (isSubmitting) return

    const nextErrors: ProfileErrors = {}
    const trimmedFirstName = firstName.trim()
    const trimmedLastName = lastName.trim()
    if (trimmedFirstName === '') nextErrors.firstName = 'First name is required.'
    if (trimmedLastName === '') nextErrors.lastName = 'Last name is required.'

    setErrors(nextErrors)
    setFeedback(null)
    if (Object.keys(nextErrors).length > 0) return

    const payload: ProfileUpdateRequest = {
      first_name: trimmedFirstName,
      last_name: trimmedLastName,
    }

    setIsSubmitting(true)
    try {
      const updatedUser = await apiClient.request<AuthUser>('/api/v1/auth/me', {
        method: 'PATCH',
        body: JSON.stringify(payload),
      })
      updateUser(updatedUser)
      setFirstName(updatedUser.first_name)
      setLastName(updatedUser.last_name)
      setFeedback({ kind: 'success', message: 'Your profile has been updated.' })
    } catch {
      setFeedback({
        kind: 'error',
        message: 'Unable to update your profile. Please try again.',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="p-5 sm:p-6" aria-labelledby="profile-settings-title">
      <div>
        <h2 id="profile-settings-title" className="text-lg font-bold text-slate-900">
          Profile details
        </h2>
        <p className="mt-1 max-w-prose text-sm leading-6 text-slate-600">
          Keep the name shown across academy operations up to date.
        </p>
      </div>

      <form className="mt-5 space-y-5" aria-busy={isSubmitting} onSubmit={handleSubmit} noValidate>
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <label className="text-sm font-semibold text-slate-800" htmlFor="settings-first-name">
              First name
            </label>
            <input
              id="settings-first-name"
              data-modal-initial-focus
              autoComplete="given-name"
              aria-describedby={errors.firstName ? 'settings-first-name-error' : undefined}
              aria-invalid={errors.firstName ? 'true' : undefined}
              className={inputClassName}
              disabled={isSubmitting}
              value={firstName}
              onChange={(event) => setFirstName(event.target.value)}
            />
            {errors.firstName && <p id="settings-first-name-error" className="mt-2 text-sm font-medium text-red-700">{errors.firstName}</p>}
          </div>
          <div>
            <label className="text-sm font-semibold text-slate-800" htmlFor="settings-last-name">
              Last name
            </label>
            <input
              id="settings-last-name"
              autoComplete="family-name"
              aria-describedby={errors.lastName ? 'settings-last-name-error' : undefined}
              aria-invalid={errors.lastName ? 'true' : undefined}
              className={inputClassName}
              disabled={isSubmitting}
              value={lastName}
              onChange={(event) => setLastName(event.target.value)}
            />
            {errors.lastName && <p id="settings-last-name-error" className="mt-2 text-sm font-medium text-red-700">{errors.lastName}</p>}
          </div>
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <label className="text-sm font-semibold text-slate-800" htmlFor="settings-email">Email address</label>
            <input id="settings-email" className={inputClassName} readOnly value={user.email} />
          </div>
          <div>
            <label className="text-sm font-semibold text-slate-800" htmlFor="settings-role">Role</label>
            <input id="settings-role" className={inputClassName} readOnly value={formatRole(user.role)} />
          </div>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div aria-live="polite">
            {feedback && <p className={`text-sm font-medium ${feedback.kind === 'success' ? 'text-emerald-700' : 'text-red-700'}`} role={feedback.kind === 'error' ? 'alert' : 'status'}>{feedback.message}</p>}
          </div>
          <button type="submit" aria-busy={isSubmitting} className="min-h-11 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-wait disabled:bg-slate-500" disabled={isSubmitting}>
            {isSubmitting ? 'Saving…' : 'Save profile'}
          </button>
        </div>
      </form>
    </section>
  )
}
