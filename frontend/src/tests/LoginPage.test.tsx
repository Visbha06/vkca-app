// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { ApiClientError } from '../api/client'
import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import LoginPage from '../pages/LoginPage'

afterEach(cleanup)

function LocationProbe() {
  const location = useLocation()
  return <p>Location: {location.pathname}</p>
}

function renderLogin(
  overrides: Partial<AuthContextValue> = {},
  initialEntry = '/login?redirect=%2Fplayers',
) {
  const value: AuthContextValue = {
    user: null,
    accessToken: null,
    isAuthenticated: false,
    isInitializing: false,
    isLoginPending: false,
    isLogoutPending: false,
    login: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn().mockResolvedValue(undefined),
    refreshSession: vi.fn().mockResolvedValue(false),
    updateUser: vi.fn(),
    ...overrides,
  }

  render(
    <AuthContext.Provider value={value}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="*" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )

  return value
}

function submitCredentials() {
  fireEvent.change(screen.getByRole('textbox', { name: 'Email address' }), {
    target: { value: 'coach@vkca.test' },
  })
  fireEvent.change(screen.getByLabelText('Password'), {
    target: { value: 'WrongPassword!1' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Log in' }))
}

describe('LoginPage', () => {
  it('renders the branded email and password form', () => {
    renderLogin()

    expect(screen.getByRole('heading', { name: 'Sign in to your account' })).toBeInTheDocument()
    expect(screen.getAllByText('VK Cricket Academy')).not.toHaveLength(0)
    expect(screen.getByRole('textbox', { name: 'Email address' })).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password')
    expect(screen.getByRole('button', { name: 'Log in' })).toBeInTheDocument()
  })

  it('shows the session-expired message after a failed token refresh', () => {
    renderLogin({}, '/login?reason=session-expired')

    expect(screen.getByRole('status')).toHaveTextContent(
      'Your session has expired. Please sign in again.',
    )
  })

  it('shows confirmation after a successful password change', () => {
    renderLogin({}, '/login?reason=password-changed')

    expect(screen.getByRole('status')).toHaveTextContent(
      'Your password was changed. Please sign in again.',
    )
  })

  it('shows field errors and does not submit when required fields are empty', () => {
    const { login } = renderLogin()

    fireEvent.click(screen.getByRole('button', { name: 'Log in' }))

    expect(screen.getByText('Email is required.')).toBeInTheDocument()
    expect(screen.getByText('Password is required.')).toBeInTheDocument()
    expect(login).not.toHaveBeenCalled()
  })

  it('submits from the form when Enter is used and returns to the preserved route', async () => {
    const { login } = renderLogin()
    const email = screen.getByRole('textbox', { name: 'Email address' })
    const password = screen.getByLabelText('Password')

    fireEvent.change(email, { target: { value: 'coach@vkca.test' } })
    fireEvent.change(password, { target: { value: 'StrongPassword!1' } })
    fireEvent.keyDown(password, { key: 'Enter', code: 'Enter' })
    fireEvent.submit(password.closest('form')!)

    await waitFor(() => expect(login).toHaveBeenCalledWith('coach@vkca.test', 'StrongPassword!1'))
    expect(await screen.findByText('Location: /players')).toBeInTheDocument()
  })

  it('toggles password visibility with an accessible control', () => {
    renderLogin()
    const password = screen.getByLabelText('Password')

    fireEvent.click(screen.getByRole('button', { name: 'Show password' }))
    expect(password).toHaveAttribute('type', 'text')

    fireEvent.click(screen.getByRole('button', { name: 'Hide password' }))
    expect(password).toHaveAttribute('type', 'password')
  })

  it('communicates a busy state and disables the login button while submission is pending', () => {
    renderLogin({ isLoginPending: true })

    const button = screen.getByRole('button', { name: 'Logging in' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(button.querySelector('.animate-spin')).toBeInTheDocument()
    expect(screen.getByText('Signing in…')).toHaveClass('sr-only')
  })

  it('shows the generic credential error for an unauthorized response', async () => {
    renderLogin({
      login: vi.fn().mockRejectedValue(
        new ApiClientError(401, { detail: 'User does not exist: coach@vkca.test' }),
      ),
    })

    submitCredentials()

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password.')
    expect(screen.queryByText(/user does not exist/i)).not.toBeInTheDocument()
  })

  it('shows a safe generic error for network and server failures', async () => {
    renderLogin({ login: vi.fn().mockRejectedValue(new TypeError('Failed to fetch raw host')) })

    submitCredentials()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to sign in right now. Please try again.',
    )
    expect(screen.queryByText(/raw host/i)).not.toBeInTheDocument()
  })

  it('shows the safe rate-limit message without exposing backend details', async () => {
    renderLogin({
      login: vi.fn().mockRejectedValue(
        new ApiClientError(429, { detail: 'Rate limit exceeded for account 42' }),
      ),
    })

    submitCredentials()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Too many sign-in attempts. Please wait and try again.',
    )
    expect(screen.queryByText(/account 42/i)).not.toBeInTheDocument()
  })
})
