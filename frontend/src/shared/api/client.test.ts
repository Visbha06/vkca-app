// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  ApiClient,
  ApiClientError,
  SESSION_EXPIRED_LOGIN_PATH,
} from '@shared/api/client'

const API_BASE_URL = 'https://api.vkca.test'
const PROTECTED_PATH = '/api/v1/players'
const REFRESH_URL = `${API_BASE_URL}/api/v1/auth/refresh`

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function requestHeaders(fetchMock: ReturnType<typeof vi.fn>, callIndex: number) {
  const init = fetchMock.mock.calls[callIndex]?.[1] as RequestInit | undefined
  return new Headers(init?.headers)
}

function createAuthenticatedClient() {
  const redirect = vi.fn()
  const onSessionExpired = vi.fn()
  const client = new ApiClient(API_BASE_URL, redirect)

  client.setAuthHandlers({ onSessionExpired })
  client.setAccessToken('expired-access-token')

  return { client, onSessionExpired, redirect }
}

beforeEach(() => {
  document.cookie = 'csrf_token=csrf-value; path=/'
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ApiClient token refresh interceptor', () => {
  it('refreshes once and retries the original request with the new token', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: 'Not authenticated' }, 401))
      .mockResolvedValueOnce(
        jsonResponse({ access_token: 'fresh-access-token', token_type: 'bearer' }),
      )
      .mockResolvedValueOnce(jsonResponse({ players: ['Anika'] }))
    vi.stubGlobal('fetch', fetchMock)
    const { client, onSessionExpired, redirect } =
      createAuthenticatedClient()

    await expect(client.request(PROTECTED_PATH)).resolves.toEqual({
      players: ['Anika'],
    })

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(fetchMock.mock.calls[1]?.[0]).toBe(REFRESH_URL)
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      method: 'POST',
      credentials: 'include',
    })
    expect(requestHeaders(fetchMock, 0).get('Authorization')).toBe(
      'Bearer expired-access-token',
    )
    expect(requestHeaders(fetchMock, 1).get('X-CSRF-Token')).toBe('csrf-value')
    expect(requestHeaders(fetchMock, 2).get('Authorization')).toBe(
      'Bearer fresh-access-token',
    )
    expect(client.getAccessToken()).toBe('fresh-access-token')
    expect(onSessionExpired).not.toHaveBeenCalled()
    expect(redirect).not.toHaveBeenCalled()
  })

  it('clears authentication and redirects with a safe reason when refresh fails', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: 'Not authenticated' }, 401))
      .mockResolvedValueOnce(jsonResponse({ detail: 'CSRF token invalid' }, 403))
      .mockResolvedValueOnce(jsonResponse({ public: true }))
    vi.stubGlobal('fetch', fetchMock)
    const { client, onSessionExpired, redirect } = createAuthenticatedClient()

    await expect(client.request(PROTECTED_PATH)).rejects.toMatchObject({
      status: 403,
    })

    expect(onSessionExpired).toHaveBeenCalledOnce()
    expect(redirect).toHaveBeenCalledOnce()
    expect(redirect).toHaveBeenCalledWith(SESSION_EXPIRED_LOGIN_PATH)

    await client.request('/api/v1/public')
    expect(requestHeaders(fetchMock, 2).has('Authorization')).toBe(false)
  })

  it('shares one in-flight refresh across simultaneous 401 responses', async () => {
    let protectedRequestCount = 0
    let refreshRequestCount = 0
    let resolveRefresh: ((response: Response) => void) | undefined
    const refreshResponse = new Promise<Response>((resolve) => {
      resolveRefresh = resolve
    })
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (String(input) === REFRESH_URL) {
        refreshRequestCount += 1
        return refreshResponse
      }

      protectedRequestCount += 1
      if (protectedRequestCount <= 3) {
        return Promise.resolve(jsonResponse({ detail: 'Not authenticated' }, 401))
      }

      return Promise.resolve(jsonResponse({ recovered: true }))
    })
    vi.stubGlobal('fetch', fetchMock)
    const { client } = createAuthenticatedClient()

    const requests = [
      client.request(PROTECTED_PATH),
      client.request(PROTECTED_PATH),
      client.request(PROTECTED_PATH),
    ]

    await vi.waitFor(() => expect(refreshRequestCount).toBe(1))
    resolveRefresh?.(
      jsonResponse({ access_token: 'shared-access-token', token_type: 'bearer' }),
    )

    await expect(Promise.all(requests)).resolves.toEqual([
      { recovered: true },
      { recovered: true },
      { recovered: true },
    ])
    expect(refreshRequestCount).toBe(1)
    expect(protectedRequestCount).toBe(6)
  })

  it('does not start another refresh when the one allowed retry also returns 401', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: 'Expired access token' }, 401))
      .mockResolvedValueOnce(
        jsonResponse({ access_token: 'fresh-but-rejected', token_type: 'bearer' }),
      )
      .mockResolvedValueOnce(jsonResponse({ detail: 'Session revoked' }, 401))
    vi.stubGlobal('fetch', fetchMock)
    const { client, onSessionExpired, redirect } = createAuthenticatedClient()

    await expect(client.request(PROTECTED_PATH)).rejects.toBeInstanceOf(ApiClientError)

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(
      fetchMock.mock.calls.filter(([input]) => String(input) === REFRESH_URL),
    ).toHaveLength(1)
    expect(onSessionExpired).toHaveBeenCalledOnce()
    expect(redirect).toHaveBeenCalledWith(SESSION_EXPIRED_LOGIN_PATH)
  })
})
