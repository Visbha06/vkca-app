// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import HomeSchedule from '../../../pages/home/HomeSchedule'
import { dashboardFixture } from '../test/dashboardFixture'
import DashboardLoadingState from './DashboardLoadingState'

afterEach(cleanup)

describe('dashboard responsive accessibility contract', () => {
  it('uses structural responsive classes and wrapping-safe section boundaries', () => {
    const dashboard = dashboardFixture()
    const { container } = render(
      <MemoryRouter>
        <HomeSchedule
          upcomingEvents={dashboard.upcoming_events}
          context={dashboard.context}
          onRetry={vi.fn()}
          role="head coach"
        />
      </MemoryRouter>,
    )

    const composition = container.firstElementChild
    expect(composition).toHaveClass('grid', 'min-w-0', 'lg:grid-cols-3')
    expect(screen.getByRole('region', { name: 'Upcoming events' })).toHaveClass(
      'min-w-0',
    )
    expect(
      screen.getByRole('region', { name: 'Recent academy activity' }),
    ).toHaveClass('min-w-0')
    expect(screen.getByRole('link', { name: 'View calendar' })).toHaveClass(
      'min-h-11',
    )
    expect(screen.getByRole('link', { name: 'View all activity' })).toHaveClass(
      'min-h-11',
    )
  })

  it('keeps unavailable sections announced and keyboard retry actions usable', () => {
    const retry = vi.fn()
    render(
      <MemoryRouter>
        <HomeSchedule
          upcomingEvents={{
            status: 'unavailable',
            message: 'Upcoming events are temporarily unavailable.',
            retryable: true,
          }}
          context={{
            status: 'unavailable',
            message: 'Team context is temporarily unavailable.',
            retryable: true,
          }}
          onRetry={retry}
          role="assistant coach"
        />
      </MemoryRouter>,
    )

    expect(screen.getAllByRole('alert')).toHaveLength(2)
    const eventRetry = screen.getByRole('button', {
      name: 'Retry upcoming events',
    })
    const contextRetry = screen.getByRole('button', {
      name: 'Retry dashboard context',
    })
    expect(eventRetry).toHaveClass('min-h-11')
    expect(contextRetry).toHaveClass('min-h-11')
    contextRetry.focus()
    expect(contextRetry).toHaveFocus()
    fireEvent.click(contextRetry)
    expect(retry).toHaveBeenCalledOnce()
  })

  it('limits loading motion to motion-safe preferences', () => {
    render(<DashboardLoadingState />)
    const loading = screen.getByRole('status', { name: 'Loading dashboard' })
    const skeleton = loading.querySelector('[aria-hidden="true"]')
    expect(skeleton).toHaveClass('motion-safe:animate-pulse')
    expect(skeleton).not.toHaveClass('animate-pulse')
  })
})
