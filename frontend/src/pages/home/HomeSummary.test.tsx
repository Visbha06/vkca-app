// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { dashboardFixture } from '@features/dashboard/test/dashboardFixture'
import HomeSummary from './HomeSummary'

afterEach(cleanup)

describe('HomeSummary', () => {
  it('renders all three live summary values and participant semantics', () => {
    const dashboard = dashboardFixture()
    render(<HomeSummary summary={dashboard.summary} onRetry={vi.fn()} />)

    const summary = screen.getByRole('region', { name: 'Academy summary' })
    expect(within(summary).getByText('Batting fundamentals')).toBeVisible()
    expect(within(summary).getByText('U15 Falcons vs Northside CC')).toBeVisible()
    expect(within(summary).getByText('42')).toBeVisible()
    expect(within(summary).getByText('Across 4 teams')).toBeVisible()
    expect(within(summary).queryByText('84')).not.toBeInTheDocument()
  })

  it('renders internal home/away labels and Player team summaries', () => {
    const dashboard = dashboardFixture()
    if (dashboard.summary.next_match.status !== 'ready') {
      throw new Error('Dashboard fixture must include a ready next match')
    }
    render(
      <HomeSummary
        onRetry={vi.fn()}
        summary={{
          ...dashboard.summary,
          next_match: {
            status: 'ready',
            data: {
              ...dashboard.summary.next_match.data,
              participants: {
                kind: 'internal',
                home_team: {
                  id: '66666666-6666-4666-8666-666666666666',
                  name: 'U13 Falcons',
                },
                away_team: {
                  id: '33333333-3333-4333-8333-333333333333',
                  name: 'U15 Falcons',
                },
              },
            },
          },
          player_slot: {
            status: 'ready',
            data: {
              kind: 'player_teams',
              team_count: 2,
              team_names: ['U13 Falcons', 'U15 Falcons'],
            },
          },
        }}
      />,
    )

    expect(screen.getByText('U13 Falcons vs U15 Falcons')).toBeVisible()
    expect(screen.getByText('2 teams')).toBeVisible()
    expect(screen.getByText('U13 Falcons, U15 Falcons')).toBeVisible()
  })

  it('keeps empty and unavailable slots explicit and retryable', () => {
    const dashboard = dashboardFixture()
    const onRetry = vi.fn()
    render(
      <HomeSummary
        onRetry={onRetry}
        summary={{
          ...dashboard.summary,
          training: { status: 'empty', message: 'No upcoming training.' },
          next_match: {
            status: 'unavailable',
            message: 'Matches are temporarily unavailable.',
            retryable: true,
          },
        }}
      />,
    )

    const emptyMessage = screen.getByText('No upcoming training.')
    const unavailableMessage = screen.getByText(
      'Matches are temporarily unavailable.',
    )
    expect(emptyMessage).toBeVisible()
    expect(emptyMessage.closest('[role="alert"]')).toBeNull()
    expect(unavailableMessage).toBeVisible()
    expect(unavailableMessage.closest('[role="alert"]')).toBe(
      screen.getByRole('alert'),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Retry next match' }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('keeps unlinked summary guidance informational', () => {
    render(
      <HomeSummary
        onRetry={vi.fn()}
        summary={{
          training: { status: 'unlinked', message: 'Link your player profile.' },
          next_match: { status: 'unlinked', message: 'Link your player profile.' },
          player_slot: { status: 'unlinked', message: 'Link your player profile.' },
        }}
      />,
    )

    expect(screen.getAllByText('Link your player profile.')).toHaveLength(3)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
