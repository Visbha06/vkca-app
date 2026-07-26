import { readCsrfToken } from './csrf'

interface ApiError {
  detail: string
}

interface RefreshResponse {
  access_token: string
  token_type: 'bearer'
}

const DEFAULT_API_BASE_URL = import.meta.env.DEV ? 'http://localhost:8000' : ''
const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])
const REFRESH_PATH = '/api/v1/auth/refresh'
const NON_REFRESHABLE_PATHS = new Set([
  '/api/v1/auth/login',
  REFRESH_PATH,
  '/api/v1/auth/logout',
])

export const SESSION_EXPIRED_LOGIN_PATH = '/login?reason=session-expired'

interface AuthHandlers {
  onAccessTokenRefreshed: (accessToken: string) => void
  onSessionExpired: () => void
}

type RedirectHandler = (path: string) => void

function isApiError(value: unknown): value is ApiError {
  return (
    typeof value === 'object' &&
    value !== null &&
    'detail' in value &&
    typeof value.detail === 'string'
  )
}

function isRefreshResponse(value: unknown): value is RefreshResponse {
  return (
    typeof value === 'object' &&
    value !== null &&
    'access_token' in value &&
    typeof value.access_token === 'string' &&
    value.access_token.length > 0 &&
    'token_type' in value &&
    value.token_type === 'bearer'
  )
}

function redirectInBrowser(path: string) {
  if (typeof window === 'undefined') return

  queueMicrotask(() => {
    window.history.replaceState(window.history.state, '', path)
    window.dispatchEvent(new PopStateEvent('popstate'))
  })
}

async function readErrorBody(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    return null
  }
}

export class ApiClientError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, body: unknown) {
    const message = isApiError(body)
      ? body.detail
      : `API request failed with status ${status}`
    super(message)
    this.name = 'ApiClientError'
    this.status = status
    this.body = body
  }
}

export class ApiClient {
  private accessToken: string | null = null
  private authHandlers: AuthHandlers | null = null
  private refreshPromise: Promise<string> | null = null
  private sessionExpiryHandled = false
  private readonly baseUrl: string
  private readonly redirect: RedirectHandler

  constructor(baseUrl: string, redirect: RedirectHandler = redirectInBrowser) {
    this.baseUrl = baseUrl.replace(/\/$/, '')
    this.redirect = redirect
  }

  setAccessToken(accessToken: string | null) {
    this.accessToken = accessToken
    if (accessToken !== null) this.sessionExpiryHandled = false
  }

  getAccessToken() {
    return this.accessToken
  }

  setAuthHandlers(authHandlers: AuthHandlers | null) {
    this.authHandlers = authHandlers
  }

  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const normalizedPath = path.startsWith('/') ? path : `/${path}`
    const tokenUsed = this.accessToken
    let response = await this.send(normalizedPath, options)

    if (
      response.status === 401 &&
      tokenUsed !== null &&
      !NON_REFRESHABLE_PATHS.has(normalizedPath)
    ) {
      if (this.accessToken === tokenUsed) {
        await this.refreshAccessToken()
      }

      response = await this.send(normalizedPath, options)
      if (response.status === 401) this.handleSessionExpired()
    }

    return this.parseResponse<T>(response)
  }

  private async send(path: string, options: RequestInit) {
    const method = (options.method ?? 'GET').toUpperCase()
    const headers = new Headers(options.headers)

    if (this.accessToken !== null && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${this.accessToken}`)
    }

    const csrfToken = readCsrfToken()
    if (
      MUTATING_METHODS.has(method) &&
      csrfToken !== null &&
      !headers.has('X-CSRF-Token')
    ) {
      headers.set('X-CSRF-Token', csrfToken)
    }

    if (
      typeof options.body === 'string' &&
      !headers.has('Content-Type')
    ) {
      headers.set('Content-Type', 'application/json')
    }

    return fetch(`${this.baseUrl}${path}`, {
      ...options,
      method,
      credentials: 'include',
      headers,
    })
  }

  private async parseResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      throw new ApiClientError(response.status, await readErrorBody(response))
    }

    if (response.status === 204) {
      return undefined as T
    }

    return (await response.json()) as T
  }

  private refreshAccessToken() {
    if (this.refreshPromise === null) {
      this.refreshPromise = this.performTokenRefresh().finally(() => {
        this.refreshPromise = null
      })
    }

    return this.refreshPromise
  }

  private async performTokenRefresh() {
    try {
      const headers = new Headers()
      const csrfToken = readCsrfToken()
      if (csrfToken !== null) headers.set('X-CSRF-Token', csrfToken)

      const response = await fetch(`${this.baseUrl}${REFRESH_PATH}`, {
        method: 'POST',
        credentials: 'include',
        headers,
      })

      if (!response.ok) {
        throw new ApiClientError(response.status, await readErrorBody(response))
      }

      const body: unknown = await response.json()
      if (!isRefreshResponse(body)) {
        throw new Error('Invalid token refresh response')
      }

      this.setAccessToken(body.access_token)
      this.authHandlers?.onAccessTokenRefreshed(body.access_token)
      return body.access_token
    } catch (error) {
      this.handleSessionExpired()
      throw error
    }
  }

  private handleSessionExpired() {
    if (this.sessionExpiryHandled) return

    this.sessionExpiryHandled = true
    this.accessToken = null
    try {
      this.authHandlers?.onSessionExpired()
    } finally {
      this.redirect(SESSION_EXPIRED_LOGIN_PATH)
    }
  }
}

const configuredApiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL

export const apiClient = new ApiClient(configuredApiBaseUrl)
