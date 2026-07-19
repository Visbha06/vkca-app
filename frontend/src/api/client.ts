import { readCsrfToken } from '../auth/utils'
import type { ApiError } from '../auth/types'

const DEFAULT_API_BASE_URL = import.meta.env.DEV ? 'http://localhost:8000' : ''
const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

function isApiError(value: unknown): value is ApiError {
  return (
    typeof value === 'object' &&
    value !== null &&
    'detail' in value &&
    typeof value.detail === 'string'
  )
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

class ApiClient {
  private accessToken: string | null = null
  private readonly baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '')
  }

  setAccessToken(accessToken: string | null) {
    this.accessToken = accessToken
  }

  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
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

    const normalizedPath = path.startsWith('/') ? path : `/${path}`
    const response = await fetch(`${this.baseUrl}${normalizedPath}`, {
      ...options,
      method,
      credentials: 'include',
      headers,
    })

    if (!response.ok) {
      throw new ApiClientError(response.status, await readErrorBody(response))
    }

    if (response.status === 204) {
      return undefined as T
    }

    return (await response.json()) as T
  }
}

const configuredApiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL

export const apiClient = new ApiClient(configuredApiBaseUrl)
