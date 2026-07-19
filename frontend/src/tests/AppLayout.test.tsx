// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import AppLayout from '../layouts/AppLayout'
import { useSidebar } from '../layouts/SidebarContext'

afterEach(cleanup)

const authValue: AuthContextValue = {
  user: null,
  accessToken: null,
  isAuthenticated: true,
  isInitializing: false,
  isLoginPending: false,
  isLogoutPending: false,
  login: vi.fn(),
  logout: vi.fn(),
  refreshSession: vi.fn(),
}

function ContextProbe() {
  const { expanded, mobileOpen } = useSidebar()

  return (
    <p>
      Sidebar context: {expanded ? 'expanded' : 'collapsed'},{' '}
      {mobileOpen ? 'open' : 'closed'}
    </p>
  )
}

function renderLayout(child = <h1>Test content</h1>) {
  render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={child} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

describe('AppLayout', () => {
  it('renders the application sidebar and main content area', () => {
    renderLayout()

    expect(screen.getByLabelText('Application sidebar')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Primary navigation' })).toBeInTheDocument()
    expect(screen.getByRole('main')).toContainElement(
      screen.getByRole('heading', { name: 'Test content' }),
    )
    expect(
      screen.getByRole('link', { name: 'Skip to main content' }),
    ).toHaveAttribute('href', '#main-content')
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content')
    expect(screen.getByRole('button', { name: 'Log out' })).toBeInTheDocument()
  })

  it('provides the default sidebar state to routed content', () => {
    renderLayout(<ContextProbe />)

    expect(
      screen.getByText('Sidebar context: expanded, closed'),
    ).toBeInTheDocument()
  })
})
