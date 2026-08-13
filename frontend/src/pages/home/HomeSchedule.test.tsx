// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import { dashboardFixture, playerDashboardFixture } from '@features/dashboard/test/dashboardFixture'
import HomeSchedule from './HomeSchedule'

afterEach(cleanup)

function renderSchedule(
  dashboard = dashboardFixture(),
  onRetry = vi.fn(),
) {
  return {
    onRetry,
    ...render(
      <MemoryRouter>
        <HomeSchedule
          upcomingEvents={dashboard.upcoming_events}
          context={dashboard.context}
          onRetry={onRetry}
          role={dashboard.user.role}
        />
      </MemoryRouter>,
    ),
  }
}

describe('HomeSchedule', () => {
  it('renders live event rows without location or venue data', () => {
    renderSchedule()

    const events = screen.getByRole('region', { name: 'Upcoming events' })
    expect(within(events).getByText('Batting fundamentals')).toBeVisible()
    expect(within(events).getByText('U15')).toBeVisible()
    expect(events).not.toHaveTextContent('Indoor Net')
    expect(events).not.toHaveTextContent('Academy Ground')
    expect(events).not.toHaveTextContent('Riverside Oval')
  })

  it('renders Head Coach activity and scoped My Teams context', () => {
    renderSchedule()
    expect(
      screen.getByRole('region', { name: 'Recent academy activity' }),
    ).toHaveTextContent('Asha Coach added Rohan Player')

    cleanup()
    renderSchedule(playerDashboardFixture())
    const teams = screen.getByRole('region', { name: 'My teams' })
    expect(teams).toHaveTextContent('U15 Falcons')
    expect(teams).toHaveTextContent('12 active players')
    expect(screen.queryByText('Asha Coach added Rohan Player')).not.toBeInTheDocument()
  })

  it('renders explicit event and context empty states', () => {
    renderSchedule(playerDashboardFixture({ hasEvents: false, hasTeams: false }))

    expect(screen.getByText('No upcoming events in your scope.')).toBeVisible()
    expect(screen.getByText('You are not on a team yet.')).toBeVisible()
  })

  it('isolates partial failures and exposes a section retry', () => {
    const dashboard = dashboardFixture({
      upcoming_events: {
        status: 'unavailable',
        message: 'Upcoming events are temporarily unavailable.',
        retryable: true,
      },
    })
    const { onRetry } = renderSchedule(dashboard)

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Upcoming events are temporarily unavailable.',
    )
    expect(screen.getByText('Asha Coach added Rohan Player')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Retry upcoming events' }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
})
