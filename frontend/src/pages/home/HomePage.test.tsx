// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import { AuthContext, type AuthContextValue } from '@features/auth'
import HomePage from '@/pages/home/HomePage'

vi.mock('@features/audit/api/businessAuditApi', () => ({
  fetchBusinessAuditActors: vi.fn(),
  fetchBusinessAuditEvents: vi.fn(),
  fetchRecentBusinessAudit: vi.fn().mockResolvedValue({ events: [] }),
}))

const auth: AuthContextValue = {
  user: {
    id: 'head-coach-1',
    first_name: 'Asha',
    last_name: 'Coach',
    email: 'asha@example.com',
    role: 'head coach',
    is_active: true,
    created_at: '',
    updated_at: '',
    session: {
      session_id: 'session-1',
      created_at: '',
      last_used_at: '',
      expires_at: '',
    },
  },
  accessToken: 'token',
  isAuthenticated: true,
  isInitializing: false,
  isLoginPending: false,
  isLogoutPending: false,
  login: vi.fn(),
  logout: vi.fn(),
  refreshSession: vi.fn(),
  updateUser: vi.fn(),
}

afterEach(cleanup)

function renderHomePage() {
  render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

describe('HomePage', () => {
  it('renders a personal academy dashboard introduction', () => {
    renderHomePage()

    expect(
      screen.getByRole('heading', {
        level: 1,
        name: 'Good evening, Coach',
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Here’s what’s happening at the academy.'),
    ).toBeInTheDocument()
  })

  it('shows the academy summary, events, and recent activity', () => {
    renderHomePage()

    const summary = screen.getByRole('region', { name: 'Academy summary' })
    expect(
      within(summary).getByRole('heading', { name: 'Upcoming training' }),
    ).toBeInTheDocument()
    expect(
      within(summary).getByRole('heading', { name: 'Next match' }),
    ).toBeInTheDocument()
    expect(
      within(summary).getByRole('heading', { name: 'Active players' }),
    ).toBeInTheDocument()
    expect(within(summary).getByText('84')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Upcoming events' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Recent academy activity' }),
    ).toBeInTheDocument()
  })

  it('offers the approved quick actions', () => {
    renderHomePage()

    const actions = screen.getByRole('navigation', { name: 'Quick actions' })
    expect(within(actions).getByRole('link', { name: 'Add player' })).toHaveAttribute(
      'href',
      '/players?action=add',
    )
    expect(within(actions).getByRole('link', { name: 'Create match' })).toHaveAttribute(
      'href',
      '/teams',
    )
    expect(
      within(actions).getByRole('link', { name: 'Schedule event' }),
    ).toHaveAttribute('href', '/calendar')
  })
})
