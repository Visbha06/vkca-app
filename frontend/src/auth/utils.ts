const CSRF_COOKIE_NAME = 'csrf_token'

export function readCsrfToken(): string | null {
  if (typeof document === 'undefined') {
    return null
  }

  const cookiePrefix = `${CSRF_COOKIE_NAME}=`
  const csrfCookie = document.cookie
    .split(';')
    .map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith(cookiePrefix))

  if (csrfCookie === undefined) {
    return null
  }

  const value = csrfCookie.slice(cookiePrefix.length)
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}
