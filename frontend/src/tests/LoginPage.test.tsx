// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import LoginPage from '../pages/LoginPage'

afterEach(cleanup)

function LocationProbe() {
  const location = useLocation()
  return <p>Location: {location.pathname}</p>
}

function renderLogin(overrides: Partial<AuthContextValue> = {}) {
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
    ...overrides,
  }

  render(
    <AuthContext.Provider value={value}>
      <MemoryRouter initialEntries={['/login?redirect=%2Fplayers']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="*" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )

  return value
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

  it('disables the login button while submission is pending', () => {
    renderLogin({ isLoginPending: true })

    expect(screen.getByRole('button', { name: 'Logging in' })).toBeDisabled()
  })
})
