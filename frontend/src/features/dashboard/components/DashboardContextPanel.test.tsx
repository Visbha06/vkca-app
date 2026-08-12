// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import DashboardContextPanel from './DashboardContextPanel'
import { dashboardFixture, playerDashboardFixture } from '../test/dashboardFixture'

afterEach(cleanup)

describe('DashboardContextPanel', () => {
  it('renders the role-appropriate panel without cross-role activity data', () => {
    const headCoach = dashboardFixture()
    const { rerender } = render(
      <MemoryRouter>
        <DashboardContextPanel section={headCoach.context} onRetry={vi.fn()} role="head coach" />
      </MemoryRouter>,
    )
    expect(screen.getByRole('region', { name: 'Recent academy activity' })).toHaveTextContent('Rohan Player')

    const player = playerDashboardFixture()
    rerender(
      <MemoryRouter>
        <DashboardContextPanel section={player.context} onRetry={vi.fn()} role="player" />
      </MemoryRouter>,
    )
    expect(screen.getByRole('region', { name: 'My teams' })).toBeVisible()
    expect(screen.queryByText('Asha Coach added Rohan Player')).not.toBeInTheDocument()
  })

  it('announces unavailable context and offers a keyboard-operable retry', () => {
    const onRetry = vi.fn()
    render(
      <MemoryRouter>
        <DashboardContextPanel
          section={{ status: 'unavailable', message: 'Context is temporarily unavailable.', retryable: true }}
          onRetry={onRetry}
          role="assistant coach"
        />
      </MemoryRouter>,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('Context is temporarily unavailable.')
    const retry = screen.getByRole('button', { name: 'Retry dashboard context' })
    retry.focus()
    expect(retry).toHaveFocus()
    fireEvent.click(retry)
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('keeps the contextual region present for empty and unlinked states', () => {
    const { rerender } = render(
      <MemoryRouter>
        <DashboardContextPanel section={{ status: 'empty', message: 'No teams are currently assigned to you.' }} onRetry={vi.fn()} role="assistant coach" />
      </MemoryRouter>,
    )
    expect(screen.getByRole('region', { name: 'My teams' })).toHaveTextContent('No teams are currently assigned to you.')

    rerender(
      <MemoryRouter>
        <DashboardContextPanel section={{ status: 'unlinked', message: 'Contact your Head Coach.' }} onRetry={vi.fn()} role="player" />
      </MemoryRouter>,
    )
    expect(screen.getByRole('region', { name: 'My teams' })).toHaveTextContent('Contact your Head Coach.')
  })
})
