// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router'
import { AuthContext, type AuthContextValue } from '@features/auth'
import AppLayout from './AppLayout'
import { useSidebar } from './SidebarContext'

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
  updateUser: vi.fn(),
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

function renderLayout(child = <h1>Test content</h1>, user = authValue.user) {
  render(
    <AuthContext.Provider value={{ ...authValue, user }}>
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

  it('hides Coaches Portal navigation from player-role users', () => {
    renderLayout(<h1>Player dashboard</h1>, {
      id: 'player-1',
      first_name: 'Asha',
      last_name: 'Patel',
      email: 'asha@vkca.test',
      role: 'player',
      is_active: true,
      created_at: '',
      updated_at: '',
      session: { session_id: '', created_at: '', last_used_at: '', expires_at: '' },
    })

    expect(screen.queryByRole('link', { name: 'Coaches Portal' })).not.toBeInTheDocument()
  })
})
