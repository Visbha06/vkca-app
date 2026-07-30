// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import {
  createMemoryRouter,
  MemoryRouter,
  Route,
  Routes,
} from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { appRoutes } from '@app/router'
import { AuthContext, type AuthContextValue } from '@features/auth'
import AppLayout from './AppLayout'

afterEach(cleanup)

const authValue: AuthContextValue = {
  user: null,
  accessToken: 'test-token',
  isAuthenticated: true,
  isInitializing: false,
  isLoginPending: false,
  isLogoutPending: false,
  login: async () => undefined,
  logout: async () => undefined,
  refreshSession: async () => true,
  updateUser: () => undefined,
}

function renderSidebar(initialPath = '/') {
  const router = createMemoryRouter(appRoutes, {
    initialEntries: [initialPath],
  })

  render(
    <AuthContext.Provider value={authValue}>
      <RouterProvider router={router} />
    </AuthContext.Provider>,
  )
}

describe('sidebar', () => {
  it('shows academy branding and keeps settings in the footer controls', () => {
    renderSidebar()

    const sidebar = screen.getByLabelText('Application sidebar')
    expect(within(sidebar).getByText('VK Cricket Academy')).toBeVisible()
    expect(within(sidebar).getByText('Academy Portal')).toBeVisible()
    expect(screen.getByRole('link', { name: 'User Settings' })).toHaveAttribute(
      'title',
      'User Settings',
    )
    expect(screen.queryByText('User Settings')).not.toBeInTheDocument()
    expect(
      within(screen.getByTestId('sidebar-footer-controls')).getByRole(
        'button',
        { name: 'Log out' },
      ),
    ).toBeInTheDocument()
  })

  it('collapses and expands while keeping navigation destinations available', () => {
    renderSidebar()

    expect(screen.getByText('Player Directory')).toBeVisible()

    fireEvent.click(
      screen.getByRole('button', { name: 'Collapse sidebar' }),
    )

    expect(
      screen.getByRole('button', { name: 'Expand sidebar' }),
    ).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByText('Player Directory')).toHaveClass('md:hidden')
    expect(
      screen.getByRole('link', { name: 'Player Directory' }),
    ).toHaveAttribute('title', 'Player Directory')

    fireEvent.click(screen.getByRole('button', { name: 'Expand sidebar' }))

    expect(screen.getByText('Player Directory')).toBeVisible()
  })

  it.each(['Enter', ' '])('toggles from the keyboard with %s', (key) => {
    renderSidebar()
    const toggle = screen.getByRole('button', { name: 'Collapse sidebar' })

    toggle.focus()
    fireEvent.keyDown(toggle, { key })

    expect(
      screen.getByRole('button', { name: 'Expand sidebar' }),
    ).toHaveFocus()
  })

  it('identifies the active destination and preserves collapsed state across navigation', async () => {
    render(
      <AuthContext.Provider value={authValue}>
        <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route element={<AppLayout />}>
              <Route index element={<h1>Home page</h1>} />
              <Route path="teams" element={<h1>Teams page</h1>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>,
    )

    expect(screen.getByRole('link', { name: 'Home' })).toHaveAttribute(
      'aria-current',
      'page',
    )

    fireEvent.click(
      screen.getByRole('button', { name: 'Collapse sidebar' }),
    )
    fireEvent.click(screen.getByRole('link', { name: 'Teams' }))

    expect(
      await screen.findByRole('heading', { name: 'Teams page' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Teams' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(
      screen.getByRole('button', { name: 'Expand sidebar' }),
    ).toBeInTheDocument()
  })

  it('resizes the sidebar and main content without overlap', () => {
    renderSidebar()
    const sidebar = screen.getByLabelText('Application sidebar')
    const main = screen.getByRole('main')

    expect(sidebar).toHaveClass('w-sidebar-expanded', 'md:w-sidebar-expanded')
    expect(main).toHaveClass('md:ml-sidebar-expanded')

    fireEvent.click(
      screen.getByRole('button', { name: 'Collapse sidebar' }),
    )

    expect(sidebar).toHaveClass('w-sidebar-expanded', 'md:w-sidebar-collapsed')
    expect(sidebar).toHaveClass('md:p-2.5')
    expect(main).toHaveClass('md:ml-sidebar-collapsed')
    expect(screen.getByTestId('sidebar-footer-controls')).toHaveClass(
      'md:flex-col',
    )
    expect(
      screen.getByRole('link', { name: 'User Settings' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Expand sidebar' }),
    ).toBeInTheDocument()
  })
})
