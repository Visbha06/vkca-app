import type { Page } from '@playwright/test'

export const mockAuthUser = {
  id: '550e8400-e29b-41d4-a716-446655440000',
  first_name: 'John',
  last_name: 'Coach',
  email: 'john.coach@vkca.test',
  role: 'head coach',
  is_active: true,
  created_at: '2026-07-01T12:00:00Z',
  updated_at: '2026-07-19T12:00:00Z',
  session: {
    session_id: '660e8400-e29b-41d4-a716-446655440001',
    created_at: '2026-07-19T12:00:00Z',
    last_used_at: '2026-07-19T12:00:00Z',
    expires_at: '2026-08-18T12:00:00Z',
  },
}

export interface AuthApiState {
  authenticated: boolean
  logins: number
  logouts: number
  passwordChanges: number
  profileUpdates: number
  nextLoginStatus: number | null
  user: typeof mockAuthUser
}

export async function installAuthApiMock(
  page: Page,
  initialSession = true,
): Promise<AuthApiState> {
  const state: AuthApiState = {
    authenticated: initialSession,
    logins: 0,
    logouts: 0,
    passwordChanges: 0,
    profileUpdates: 0,
    nextLoginStatus: null,
    user: structuredClone(mockAuthUser),
  }

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const { pathname } = new URL(request.url())

    if (pathname === '/api/v1/auth/refresh' && request.method() === 'POST') {
      if (!state.authenticated) {
        await route.fulfill({ status: 401, json: { detail: 'Invalid or expired session' } })
        return
      }
      await route.fulfill({ status: 200, json: { access_token: 'restored-access-token', token_type: 'bearer' } })
      return
    }

    if (pathname === '/api/v1/auth/login' && request.method() === 'POST') {
      state.logins += 1
      if (state.nextLoginStatus !== null) {
        const status = state.nextLoginStatus
        state.nextLoginStatus = null
        await route.fulfill({ status, json: { detail: 'Invalid credentials' } })
        return
      }
      state.authenticated = true
      await route.fulfill({ status: 200, json: { access_token: 'login-access-token', token_type: 'bearer' } })
      return
    }

    if (pathname === '/api/v1/auth/me' && request.method() === 'GET') {
      await route.fulfill(
        state.authenticated
          ? { status: 200, json: state.user }
          : { status: 401, json: { detail: 'Not authenticated' } },
      )
      return
    }

    if (pathname === '/api/v1/auth/me' && request.method() === 'PATCH') {
      const profile = request.postDataJSON() as { first_name: string; last_name: string }
      state.profileUpdates += 1
      state.user.first_name = profile.first_name
      state.user.last_name = profile.last_name
      await route.fulfill({ status: 200, json: state.user })
      return
    }

    if (/^\/api\/v1\/users\/[^/]+\/change-password$/.test(pathname)) {
      state.passwordChanges += 1
      await route.fulfill({ status: 204 })
      return
    }

    if (pathname === '/api/v1/auth/logout' && request.method() === 'POST') {
      state.logouts += 1
      state.authenticated = false
      await route.fulfill({ status: 204 })
      return
    }

    await route.fulfill({ status: 404, json: { detail: 'Unhandled test route' } })
  })

  return state
}
