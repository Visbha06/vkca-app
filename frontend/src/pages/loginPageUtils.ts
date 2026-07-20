import { ApiClientError } from '../api/client'

export interface FieldErrors {
  email?: string
  password?: string
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function getRedirectTarget(redirect: string | null) {
  return redirect?.startsWith('/') && !redirect.startsWith('//') ? redirect : '/'
}

export function getLoginErrorMessage(error: unknown) {
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

export function validateCredentials(email: string, password: string) {
  const errors: FieldErrors = {}
  if (email === '') errors.email = 'Email is required.'
  else if (!EMAIL_PATTERN.test(email)) errors.email = 'Enter a valid email address.'
  if (password === '') errors.password = 'Password is required.'
  return errors
}
