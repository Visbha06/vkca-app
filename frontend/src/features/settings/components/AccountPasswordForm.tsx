import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '@shared/api/client'
import PasswordInput from '@shared/components/forms/PasswordInput'
import { useAuth, type PasswordChangeRequest } from '@features/auth'

interface PasswordErrors {
  password: string[]
  confirmation: string[]
}

const emptyErrors: PasswordErrors = { password: [], confirmation: [] }

function validatePassword(password: string) {
  const errors: string[] = []
  if (password.length < 12) errors.push('Password must be at least 12 characters.')
  if (password.length > 128) errors.push('Password must be no more than 128 characters.')
  if (!/[A-Z]/.test(password)) errors.push('Password must include an uppercase letter.')
  if (!/[a-z]/.test(password)) errors.push('Password must include a lowercase letter.')
  if (!/[0-9]/.test(password)) errors.push('Password must include a number.')
  if (!/[^A-Za-z0-9]/.test(password)) errors.push('Password must include a special character.')
  return errors
}

export default function AccountPasswordForm() {
  const { logout, user } = useAuth()
  const navigate = useNavigate()
  const [newPassword, setNewPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [errors, setErrors] = useState<PasswordErrors>(emptyErrors)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (user === null) return null
  const userId = user.id

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (isSubmitting) return

    const nextErrors: PasswordErrors = {
      password: validatePassword(newPassword),
      confirmation:
        confirmation === ''
          ? ['Please confirm your new password.']
          : confirmation !== newPassword
            ? ['Passwords must match.']
            : [],
    }
    setErrors(nextErrors)
    setSubmitError(null)
    if (nextErrors.password.length > 0 || nextErrors.confirmation.length > 0) return

    const payload: PasswordChangeRequest = {
      new_password: newPassword,
      confirm_password: confirmation,
    }
    let passwordChanged = false
    setIsSubmitting(true)
    try {
      await apiClient.request<void>(
        `/api/v1/users/${encodeURIComponent(userId)}/change-password`,
        { method: 'POST', body: JSON.stringify(payload) },
      )
      passwordChanged = true
    } catch {
      setSubmitError('Unable to change your password. Please try again.')
    } finally {
      setNewPassword('')
      setConfirmation('')
      setIsSubmitting(false)
    }

    if (passwordChanged) {
      try {
        await logout()
      } finally {
        navigate('/login?reason=password-changed', { replace: true, flushSync: true })
      }
    }
  }

  return (
    <section className="border-t border-slate-200 p-5 sm:p-6" aria-labelledby="password-settings-title">
      <div>
        <h2 id="password-settings-title" className="text-lg font-bold text-slate-900">Change password</h2>
        <p className="mt-1 max-w-prose text-sm leading-6 text-slate-600">
          Use at least 12 characters with uppercase, lowercase, a number, and a special character. Changing it signs you out everywhere.
        </p>
      </div>

      <form className="mt-5 space-y-5" aria-busy={isSubmitting} onSubmit={handleSubmit} noValidate>
        <PasswordInput id="settings-new-password" label="New password" value={newPassword} onChange={setNewPassword} disabled={isSubmitting} errors={errors.password} />
        <PasswordInput id="settings-confirm-password" label="Confirm new password" value={confirmation} onChange={setConfirmation} disabled={isSubmitting} errors={errors.confirmation} />

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div aria-live="assertive">
            {submitError && <p className="text-sm font-medium text-red-700" role="alert">{submitError}</p>}
          </div>
          <button type="submit" aria-busy={isSubmitting} className="min-h-11 rounded-lg border border-red-700 bg-white px-5 py-2.5 text-sm font-semibold text-red-700 transition-colors hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-wait disabled:border-red-300 disabled:bg-red-50 disabled:text-red-800 disabled:opacity-60" disabled={isSubmitting}>
            {isSubmitting ? 'Changing…' : 'Change password'}
          </button>
        </div>
      </form>
    </section>
  )
}
