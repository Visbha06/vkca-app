// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import { AuthContext, type AuthContextValue, type AuthUser } from '@features/auth'
import { useDashboard } from '@features/dashboard/hooks/useDashboard'
import {
  dashboardFixture,
  playerDashboardFixture,
} from '@features/dashboard/test/dashboardFixture'
import type { DashboardResponse } from '@features/dashboard/types/dashboard'
import HomePage from './HomePage'

vi.mock('@features/dashboard/hooks/useDashboard', () => ({
  useDashboard: vi.fn(),
}))

const baseUser: AuthUser = {
  id: '11111111-1111-4111-8111-111111111111',
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
}

function authValue(user: AuthUser): AuthContextValue {
  return {
    user,
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
}

const retry = vi.fn()

function renderHome(
  dashboard: DashboardResponse | null = dashboardFixture(),
  user: AuthUser = baseUser,
  state: { isFetching?: boolean; errorMessage?: string | null } = {},
) {
  vi.mocked(useDashboard).mockReturnValue({
    result: dashboard,
    isFetching: state.isFetching ?? false,
    isInitialLoading: (state.isFetching ?? false) && dashboard === null,
    errorMessage: state.errorMessage ?? null,
    retry,
  })
  render(
    <AuthContext.Provider value={authValue(user)}>
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

afterEach(cleanup)

beforeEach(() => {
  vi.clearAllMocks()
})

describe('HomePage live briefing', () => {
  it('uses the current authenticated name and role wording', () => {
    renderHome()

    expect(
      screen.getByRole('heading', { level: 1, name: 'Welcome back, Coach Asha' }),
    ).toBeVisible()
    expect(screen.getByText('Here’s what’s happening at the academy.')).toBeVisible()
  })

  it('renders loading and initial failure states without sample fallback values', () => {
    renderHome(null, baseUser, { isFetching: true })
    expect(screen.getByRole('status', { name: 'Loading dashboard' })).toBeVisible()
    expect(screen.queryByText('84')).not.toBeInTheDocument()
    expect(screen.queryByText(/Indoor Net 1/)).not.toBeInTheDocument()

    cleanup()
    renderHome(null, baseUser, { errorMessage: 'Unable to load your dashboard.' })
    fireEvent.click(screen.getByRole('button', { name: 'Retry dashboard' }))
    expect(retry).toHaveBeenCalledTimes(1)
    expect(screen.queryByText('84')).not.toBeInTheDocument()
  })

  it.each([
    ['head coach', dashboardFixture(), 'Schedule event', '/calendar'],
    [
      'assistant coach',
      dashboardFixture({
        user: { ...dashboardFixture().user, role: 'assistant coach' },
      }),
      'Schedule event',
      '/calendar',
    ],
    ['player', playerDashboardFixture(), 'View Upcoming Events', '#upcoming-events'],
    [
      'player',
      playerDashboardFixture({ hasEvents: false, hasTeams: true }),
      'View Teams',
      '/teams',
    ],
    [
      'player',
      playerDashboardFixture({ hasEvents: false, hasTeams: false }),
      'View Upcoming Events',
      '#upcoming-events',
    ],
    [
      'player',
      playerDashboardFixture({ unlinked: true }),
      'View Upcoming Events',
      '#upcoming-events',
    ],
  ] as const)(
    'renders exactly one authorized primary action for %s',
    (role, dashboard, actionName, href) => {
      const user = {
        ...baseUser,
        first_name: role === 'player' ? 'Priya' : 'Asha',
        role,
      }
      renderHome(dashboard, user)

      const actions = screen.getByRole('navigation', { name: 'Primary action' })
      const links = within(actions).getAllByRole('link')
      expect(links).toHaveLength(1)
      expect(links[0]).toHaveAccessibleName(actionName)
      expect(links[0]).toHaveAttribute('href', href)
      expect(within(actions).queryByText('Create match')).not.toBeInTheDocument()
      expect(within(actions).queryByText('Add player')).not.toBeInTheDocument()
    },
  )

  it('retains populated sections during refresh failure and retries', () => {
    renderHome(dashboardFixture(), baseUser, {
      isFetching: false,
      errorMessage: 'Unable to refresh your dashboard.',
    })

    expect(screen.getAllByText('Batting fundamentals')).toHaveLength(2)
    fireEvent.click(screen.getByRole('button', { name: 'Retry dashboard refresh' }))
    expect(retry).toHaveBeenCalledTimes(1)
  })

  it('keeps populated dashboard results labelled and exposes background refresh state', () => {
    renderHome(dashboardFixture(), baseUser, { isFetching: true })

    const results = screen.getByRole('region', { name: 'Dashboard results' })
    expect(results).toHaveAttribute('aria-busy', 'true')
    expect(within(results).getAllByText('Batting fundamentals')).toHaveLength(2)

    cleanup()
    renderHome(dashboardFixture(), baseUser, { isFetching: false })

    expect(
      screen.getByRole('region', { name: 'Dashboard results' }),
    ).toHaveAttribute('aria-busy', 'false')
  })

  it('keeps an unlinked Player limited to contact guidance', () => {
    renderHome(
      playerDashboardFixture({ unlinked: true }),
      { ...baseUser, first_name: 'Priya', role: 'player' },
    )

    expect(screen.getAllByText(/Contact your Head Coach/).length).toBeGreaterThan(0)
    expect(screen.queryByText('42')).not.toBeInTheDocument()
    expect(screen.queryByText('Northside CC')).not.toBeInTheDocument()
  })

  it('moves focus to the explicit upcoming-event state from the Player action', () => {
    renderHome(
      playerDashboardFixture({ hasEvents: false, hasTeams: false }),
      { ...baseUser, first_name: 'Priya', role: 'player' },
    )

    fireEvent.click(
      screen.getByRole('link', { name: 'View Upcoming Events' }),
    )

    expect(screen.getByRole('region', { name: 'Upcoming events' })).toHaveFocus()
  })
})
