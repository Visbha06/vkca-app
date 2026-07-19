// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import LogoutButton from '../components/LogoutButton'

const defaultAuthValue: AuthContextValue = {
  user: null,
  accessToken: null,
  isAuthenticated: true,
  isInitializing: false,
  isLoginPending: false,
  isLogoutPending: false,
  login: vi.fn(),
  logout: vi.fn(),
  refreshSession: vi.fn(),
  updateUser: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function renderLogoutButton(overrides: Partial<AuthContextValue> = {}) {
  return render(
    <AuthContext.Provider value={{ ...defaultAuthValue, ...overrides }}>
      <LogoutButton />
    </AuthContext.Provider>,
  )
}

describe('LogoutButton', () => {
  it('renders an accessible logout control and calls the logout action', () => {
    const logout = vi.fn().mockResolvedValue(undefined)
    renderLogoutButton({ logout })

    const button = screen.getByRole('button', { name: 'Log out' })

    expect(button).toHaveAttribute('title', 'Log out')
    fireEvent.click(button)
    expect(logout).toHaveBeenCalledOnce()
  })

  it('communicates the pending state and prevents duplicate logout requests', () => {
    const logout = vi.fn().mockResolvedValue(undefined)
    renderLogoutButton({ isLogoutPending: true, logout })

    const button = screen.getByRole('button', { name: 'Log out' })

    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    fireEvent.click(button)
    expect(logout).not.toHaveBeenCalled()
  })
})
