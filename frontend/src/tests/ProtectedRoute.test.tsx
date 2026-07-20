// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import GuestRoute from '../auth/GuestRoute'
import ProtectedRoute from '../auth/ProtectedRoute'

afterEach(cleanup)

function LocationProbe() {
  const location = useLocation()
  return <p>Location: {location.pathname}{location.search}</p>
}

function renderProtected(overrides: Partial<AuthContextValue> = {}) {
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

  return render(
    <AuthContext.Provider value={value}>
      <MemoryRouter initialEntries={['/players?team=under-15']}>
        <Routes>
          <Route
            path="/players"
            element={(
              <ProtectedRoute>
                <h1>Protected players</h1>
              </ProtectedRoute>
            )}
          />
          <Route path="/login" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

function renderGuest(overrides: Partial<AuthContextValue> = {}) {
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

  return render(
    <AuthContext.Provider value={value}>
      <MemoryRouter initialEntries={['/login?redirect=%2Fplayers']}>
        <Routes>
          <Route
            path="/login"
            element={(
              <GuestRoute>
                <h1>Guest login</h1>
              </GuestRoute>
            )}
          />
          <Route path="/players" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

describe('ProtectedRoute', () => {
  it('redirects unauthenticated visitors and preserves the requested path', async () => {
    renderProtected()

    await waitFor(() => {
      expect(screen.getByText('Location: /login?redirect=%2Fplayers%3Fteam%3Dunder-15')).toBeInTheDocument()
    })
    expect(screen.queryByRole('heading', { name: 'Protected players' })).not.toBeInTheDocument()
  })

  it('renders protected children for authenticated users', () => {
    renderProtected({ isAuthenticated: true })

    expect(screen.getByRole('heading', { name: 'Protected players' })).toBeInTheDocument()
  })

  it('renders nothing while authentication is initializing', () => {
    const { container } = renderProtected({ isInitializing: true })

    expect(container).toBeEmptyDOMElement()
  })
})

describe('GuestRoute', () => {
  it('renders guest content for unauthenticated visitors', () => {
    renderGuest()

    expect(screen.getByRole('heading', { name: 'Guest login' })).toBeInTheDocument()
  })

  it('redirects authenticated visitors to the preserved destination', async () => {
    renderGuest({ isAuthenticated: true, accessToken: 'test-token' })

    expect(await screen.findByText('Location: /players')).toBeInTheDocument()
  })

  it('renders nothing while authentication is initializing', () => {
    const { container } = renderGuest({ isInitializing: true })

    expect(container).toBeEmptyDOMElement()
  })
})
