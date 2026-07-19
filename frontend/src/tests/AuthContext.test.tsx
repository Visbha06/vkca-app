// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import AuthProvider from '../auth/AuthProvider'
import type { AuthUser } from '../auth/types'

const authenticatedUser: AuthUser = {
  id: 'user-1',
  first_name: 'Vikram',
  last_name: 'Kumar',
  email: 'coach@vkca.test',
  role: 'head coach',
  is_active: true,
  created_at: '2026-07-01T09:00:00Z',
  updated_at: '2026-07-19T09:00:00Z',
  session: {
    session_id: 'session-1',
    created_at: '2026-07-19T09:00:00Z',
    last_used_at: '2026-07-19T09:00:00Z',
    expires_at: '2026-08-18T09:00:00Z',
  },
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function AuthProbe() {
  const auth = useAuth()

  return (
    <div>
      <p data-testid="initializing">{String(auth.isInitializing)}</p>
      <p data-testid="authenticated">{String(auth.isAuthenticated)}</p>
      <p data-testid="login-pending">{String(auth.isLoginPending)}</p>
      <p data-testid="user-email">{auth.user?.email ?? 'none'}</p>
      <p data-testid="user-name">{auth.user?.first_name ?? 'none'}</p>
      <p data-testid="access-token">{auth.accessToken ?? 'none'}</p>
      <button
        type="button"
        onClick={() => {
          void auth.login('coach@vkca.test', 'StrongPassword!1').catch(() => undefined)
        }}
      >
        Log in
      </button>
      <button type="button" onClick={() => void auth.logout()}>
        Log out
      </button>
      <button
        type="button"
        onClick={() => {
          if (auth.user !== null) {
            auth.updateUser({ ...auth.user, first_name: 'Updated' })
          }
        }}
      >
        Update user
      </button>
    </div>
  )
}

function renderProvider() {
  return render(
    <AuthProvider>
      <AuthProbe />
    </AuthProvider>,
  )
}

describe('AuthProvider', () => {
  it('logs in, loads the current user, and stores the access token in memory', async () => {
    const request = vi
      .spyOn(apiClient, 'request')
      .mockRejectedValueOnce(new Error('No existing session'))
    const setAccessToken = vi.spyOn(apiClient, 'setAccessToken')

    renderProvider()
    await waitFor(() => expect(screen.getByTestId('initializing')).toHaveTextContent('false'))

    request
      .mockResolvedValueOnce({ access_token: 'login-token', token_type: 'bearer' })
      .mockResolvedValueOnce(authenticatedUser)
    fireEvent.click(screen.getByRole('button', { name: 'Log in' }))

    await waitFor(() => expect(screen.getByTestId('authenticated')).toHaveTextContent('true'))
    expect(screen.getByTestId('user-email')).toHaveTextContent('coach@vkca.test')
    expect(screen.getByTestId('access-token')).toHaveTextContent('login-token')
    expect(setAccessToken).toHaveBeenLastCalledWith('login-token')
  })

  it('clears the pending state when login fails', async () => {
    const request = vi
      .spyOn(apiClient, 'request')
      .mockRejectedValueOnce(new Error('No existing session'))

    renderProvider()
    await waitFor(() => expect(screen.getByTestId('initializing')).toHaveTextContent('false'))

    request.mockRejectedValueOnce(new Error('Invalid credentials'))
    fireEvent.click(screen.getByRole('button', { name: 'Log in' }))

    await waitFor(() => expect(screen.getByTestId('login-pending')).toHaveTextContent('false'))
    expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
    expect(screen.getByTestId('access-token')).toHaveTextContent('none')
  })

  it('restores a valid session when mounted', async () => {
    vi.spyOn(apiClient, 'request')
      .mockResolvedValueOnce({ access_token: 'restored-token', token_type: 'bearer' })
      .mockResolvedValueOnce(authenticatedUser)

    renderProvider()

    await waitFor(() => expect(screen.getByTestId('initializing')).toHaveTextContent('false'))
    expect(screen.getByTestId('authenticated')).toHaveTextContent('true')
    expect(screen.getByTestId('access-token')).toHaveTextContent('restored-token')
    expect(screen.getByTestId('user-email')).toHaveTextContent('coach@vkca.test')
  })

  it('finishes initialization with cleared auth when session restore fails', async () => {
    vi.spyOn(apiClient, 'request').mockRejectedValue(new Error('Expired session'))

    renderProvider()

    await waitFor(() => expect(screen.getByTestId('initializing')).toHaveTextContent('false'))
    expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
    expect(screen.getByTestId('access-token')).toHaveTextContent('none')
    expect(screen.getByTestId('user-email')).toHaveTextContent('none')
  })

  it('clears local authentication after logout', async () => {
    const request = vi
      .spyOn(apiClient, 'request')
      .mockResolvedValueOnce({ access_token: 'restored-token', token_type: 'bearer' })
      .mockResolvedValueOnce(authenticatedUser)
    const setAccessToken = vi.spyOn(apiClient, 'setAccessToken')

    renderProvider()
    await waitFor(() => expect(screen.getByTestId('authenticated')).toHaveTextContent('true'))

    request.mockResolvedValueOnce(undefined)
    fireEvent.click(screen.getByRole('button', { name: 'Log out' }))

    await waitFor(() => expect(screen.getByTestId('authenticated')).toHaveTextContent('false'))
    expect(screen.getByTestId('access-token')).toHaveTextContent('none')
    expect(screen.getByTestId('user-email')).toHaveTextContent('none')
    expect(setAccessToken).toHaveBeenLastCalledWith(null)
  })

  it('clears local authentication when server-side logout fails', async () => {
    const request = vi
      .spyOn(apiClient, 'request')
      .mockResolvedValueOnce({ access_token: 'restored-token', token_type: 'bearer' })
      .mockResolvedValueOnce(authenticatedUser)
    const setAccessToken = vi.spyOn(apiClient, 'setAccessToken')

    renderProvider()
    await waitFor(() => expect(screen.getByTestId('authenticated')).toHaveTextContent('true'))

    request.mockRejectedValueOnce(new Error('Network unavailable'))
    fireEvent.click(screen.getByRole('button', { name: 'Log out' }))

    await waitFor(() => expect(screen.getByTestId('authenticated')).toHaveTextContent('false'))
    expect(screen.getByTestId('access-token')).toHaveTextContent('none')
    expect(screen.getByTestId('user-email')).toHaveTextContent('none')
    expect(setAccessToken).toHaveBeenLastCalledWith(null)
  })

  it('updates the authenticated user without reloading the session', async () => {
    vi.spyOn(apiClient, 'request')
      .mockResolvedValueOnce({ access_token: 'restored-token', token_type: 'bearer' })
      .mockResolvedValueOnce(authenticatedUser)

    renderProvider()
    await waitFor(() => expect(screen.getByTestId('authenticated')).toHaveTextContent('true'))

    fireEvent.click(screen.getByRole('button', { name: 'Update user' }))

    expect(screen.getByTestId('user-name')).toHaveTextContent('Updated')
    expect(screen.getByTestId('authenticated')).toHaveTextContent('true')
    expect(screen.getByTestId('access-token')).toHaveTextContent('restored-token')
  })
})
