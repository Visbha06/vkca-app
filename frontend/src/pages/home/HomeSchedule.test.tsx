// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import type { ReactElement } from 'react'
import { AuthContext, type AuthContextValue, type AuthUser } from '@features/auth'
import { fetchRecentBusinessAudit } from '@features/audit/api/businessAuditApi'
import type { BusinessAuditEvent } from '@features/audit/types/businessAudit'
import HomePage from './HomePage'
import HomeSchedule from './HomeSchedule'

vi.mock('@features/audit/api/businessAuditApi', () => ({
  fetchBusinessAuditActors: vi.fn(),
  fetchBusinessAuditEvents: vi.fn(),
  fetchRecentBusinessAudit: vi.fn(),
}))

const user: AuthUser = {
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
}

const auth: AuthContextValue = {
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

function event(
  id: string,
  category: BusinessAuditEvent['action_category'],
  summary: string,
  createdAt = '2026-08-06T18:00:00-07:00',
): BusinessAuditEvent {
  return {
    id,
    actor_user_id: user.id,
    actor_display_name: 'Asha Coach',
    actor_role: 'head coach',
    action_type: `${category}.updated` as BusinessAuditEvent['action_type'],
    action_category: category,
    target_entity_type: category === 'calendar' ? 'calendar_event' : category,
    target_entity_id: `${category}-${id}`,
    target_label: `${category} target`,
    summary,
    metadata: {},
    created_at: createdAt,
    request_id: null,
  }
}

function renderWithRole(
  element: ReactElement,
  role: AuthUser['role'] = 'head coach',
) {
  render(
    <AuthContext.Provider value={{ ...auth, user: { ...user, role } }}>
      <MemoryRouter>{element}</MemoryRouter>
    </AuthContext.Provider>,
  )
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-08-06T20:00:00-07:00'))
})

afterEach(() => {
  vi.useRealTimers()
})

describe('HomeSchedule recent academy activity', () => {
  it('renders at most the latest four events with concise summaries, categories, and relative times', async () => {
    vi.mocked(fetchRecentBusinessAudit).mockResolvedValue({
      events: [
        event('1', 'player', 'Added Aarav Singh'),
        event('2', 'team', 'Updated U16 squad'),
        event('3', 'roster', 'Reordered U16 roster'),
        event('4', 'coach', 'Activated Maya Shah'),
        event('5', 'calendar', 'Scheduled Monday training'),
      ],
    })

    renderWithRole(<HomeSchedule />)

    const activity = screen.getByRole('region', { name: 'Recent academy activity' })
    await waitFor(() => expect(activity.querySelectorAll('ol > li')).toHaveLength(4))
    expect(activity).toHaveTextContent('Added Aarav Singh')
    expect(activity).toHaveTextContent('Player')
    expect(activity).toHaveTextContent('2 hours ago')
    expect(activity).not.toHaveTextContent('Scheduled Monday training')
    expect(fetchRecentBusinessAudit).toHaveBeenCalledWith(4, expect.any(AbortSignal))
  })

  it('does not render or request recent activity for Assistant Coaches and Players', async () => {
    vi.mocked(fetchRecentBusinessAudit).mockResolvedValue({ events: [] })

    renderWithRole(<HomeSchedule />, 'assistant coach')
    await waitFor(() => expect(fetchRecentBusinessAudit).not.toHaveBeenCalled())
    expect(screen.queryByRole('region', { name: 'Recent academy activity' })).not.toBeInTheDocument()

    cleanup()
    renderWithRole(<HomeSchedule />, 'player')
    await waitFor(() => expect(fetchRecentBusinessAudit).not.toHaveBeenCalled())
    expect(screen.queryByRole('region', { name: 'Recent academy activity' })).not.toBeInTheDocument()
  })

  it('shows an empty state without placeholder activity', async () => {
    vi.mocked(fetchRecentBusinessAudit).mockResolvedValue({ events: [] })

    renderWithRole(<HomeSchedule />)

    await waitFor(() => expect(screen.getByText('No recent academy activity yet.')).toBeInTheDocument())
    expect(screen.getByRole('region', { name: 'Recent academy activity' })).toBeInTheDocument()
  })

  it('isolates a retryable recent-activity failure from the rest of the dashboard', async () => {
    vi.mocked(fetchRecentBusinessAudit)
      .mockRejectedValueOnce(new Error('temporary failure'))
      .mockResolvedValueOnce({ events: [] })

    renderWithRole(<HomePage />)

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Unable to load recent academy activity.'))
    expect(screen.getByRole('heading', { name: 'Upcoming events' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(screen.getByText('No recent academy activity yet.')).toBeInTheDocument())
    expect(fetchRecentBusinessAudit).toHaveBeenCalledTimes(2)
  })

  it('links Head Coaches to the full Audit Log', async () => {
    vi.mocked(fetchRecentBusinessAudit).mockResolvedValue({ events: [] })

    renderWithRole(<HomeSchedule />)

    await waitFor(() => expect(screen.getByRole('link', { name: 'View all activity' })).toHaveAttribute('href', '/audit-log'))
  })
})
