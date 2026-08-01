// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '@features/auth'
import CalendarPage from './CalendarPage'
import useCalendarData from '../hooks/useCalendarData'
import type { CalendarEventInstance } from '../types/calendar'

vi.mock('../hooks/useCalendarData')

const mockedUseCalendarData = vi.mocked(useCalendarData)

function makeEvent(): CalendarEventInstance {
  return {
    occurrence_id: 'event-1',
    event_id: 'event-1',
    series_id: null,
    original_date: '2026-08-05',
    event_date: '2026-08-05',
    event_type: 'practice',
    name: 'Wednesday practice',
    is_all_day: false,
    start_time: '17:00:00',
    end_time: '18:30:00',
    scope_kind: 'age_group',
    age_groups: ['U13'],
    is_recurring: false,
    recurrence_summary: null,
    event_version_number: 1,
    exception_id: null,
    exception_version_number: null,
  }
}

function authValue(role: 'head coach' | 'assistant coach' | 'player'): AuthContextValue {
  return {
    user: {
      id: 'user-1',
      first_name: 'Asha',
      last_name: 'Singh',
      email: 'asha@example.test',
      role,
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      session: {
        session_id: 'session-1',
        created_at: '2026-01-01T00:00:00Z',
        last_used_at: '2026-01-01T00:00:00Z',
        expires_at: '2027-01-01T00:00:00Z',
      },
    },
    accessToken: 'token',
    isAuthenticated: true,
    isInitializing: false,
    isLoginPending: false,
    isLogoutPending: false,
    login: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn().mockResolvedValue(undefined),
    refreshSession: vi.fn().mockResolvedValue(true),
    updateUser: vi.fn(),
  }
}

function renderPage(role: 'head coach' | 'assistant coach' | 'player' = 'player') {
  const event = makeEvent()
  const hook = {
    academyToday: '2026-08-05',
    closeSelectedInstance: vi.fn(),
    detailError: null,
    events: [event],
    focusedDate: { year: 2026, month: 8, day: 5 },
    goToNextMonth: vi.fn(),
    goToPreviousMonth: vi.fn(),
    goToYear: vi.fn(),
    handleFocusDate: vi.fn(),
    isDetailLoading: false,
    isInitialLoading: false,
    isRangeLoading: false,
    isTodayLoading: false,
    navigateToMonth: vi.fn(),
    rangeError: null,
    refreshAfterMutation: vi.fn(),
    retryDetail: vi.fn(),
    retryRange: vi.fn(),
    retryToday: vi.fn(),
    selectInstance: vi.fn(),
    selectedInstance: null,
    setSelectedInstance: vi.fn(),
    todayError: null,
    todayEvents: [],
    viewMonth: { year: 2026, month: 8 },
  } as ReturnType<typeof useCalendarData>
  mockedUseCalendarData.mockReturnValue(hook)

  return render(
    <AuthContext.Provider value={authValue(role)}>
      <CalendarPage />
    </AuthContext.Provider>,
  )
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('CalendarPage', () => {
  it.each(['head coach', 'assistant coach', 'player'] as const)(
    'opens the current academy month for %s',
    (role) => {
      renderPage(role)

      expect(screen.getByRole('heading', { name: 'Calendar' })).toBeInTheDocument()
      expect(screen.getByRole('heading', { name: 'August 2026' })).toBeInTheDocument()
      expect(screen.getByRole('grid', { name: 'August 2026 calendar' })).toBeInTheDocument()
    },
  )

  it('keeps Player details read-only and restores focus after closing details', () => {
    const view = renderPage('player')
    const eventButton = screen.getByRole('button', { name: /Practice event: Wednesday practice/ })

    expect(screen.queryByRole('button', { name: /Create Event|Edit Event|Delete Event/ })).not.toBeInTheDocument()
    eventButton.focus()
    fireEvent.click(eventButton)
    expect(screen.getByRole('heading', { name: 'Wednesday practice' })).toBeInTheDocument()
    expect(screen.getByText('U13')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Close event details' }))

    expect(view.container).toContainElement(eventButton)
    expect(eventButton).toHaveFocus()
  })

  it('shows create, edit, and delete actions only to coaches', () => {
    renderPage('assistant coach')
    fireEvent.click(screen.getByRole('button', { name: 'Create Event' }))
    expect(screen.getByRole('dialog', { name: 'Create event' })).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Close create event' }))

    fireEvent.click(
      screen.getByRole('button', { name: /Practice event: Wednesday practice/ }),
    )
    expect(screen.getByRole('button', { name: 'Edit Event' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Delete Event' })).toBeVisible()
  })

  it('keeps the semantic monthly grid bounded at mobile, tablet, and desktop widths', () => {
    for (const width of [320, 768, 1440]) {
      Object.defineProperty(window, 'innerWidth', { configurable: true, value: width })
      const { unmount } = renderPage()
      const grid = screen.getByRole('grid', { name: 'August 2026 calendar' })
      expect(grid).toHaveClass('overflow-hidden')
      expect(grid).toHaveAttribute('aria-busy', 'false')
      unmount()
    }
  })
})
