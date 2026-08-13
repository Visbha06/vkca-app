// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import MyTeamsPanel from './MyTeamsPanel'

describe('MyTeamsPanel', () => {
  it('renders scoped team metadata, permitted coach context, and teams navigation', () => {
    render(
      <MemoryRouter>
        <MyTeamsPanel
          context={{
            kind: 'my_teams',
            view_all_path: '/teams',
            teams: [{
              id: '33333333-3333-4333-8333-333333333333', name: 'U15 Falcons', age_group: 'U15', active_player_count: 12,
              coaches: [{ id: '44444444-4444-4444-8444-444444444444', display_name: 'Asha Coach' }],
              next_event: { occurrence_id: 'event-1', event_date: '2026-08-12', start_time: '17:00:00', end_time: '18:30:00', name: 'Batting fundamentals', event_type: 'practice', age_groups: ['U15'] },
            }],
          }}
        />
      </MemoryRouter>,
    )

    expect(screen.getByRole('region', { name: 'My teams' })).toHaveTextContent('Asha Coach')
    expect(screen.getByText(/Batting fundamentals/)).toBeVisible()
    expect(screen.getByRole('link', { name: 'View teams' })).toHaveAttribute('href', '/teams')
  })

  it('keeps a useful no-team state inside the panel', () => {
    render(<MemoryRouter><MyTeamsPanel context={{ kind: 'my_teams', teams: [], view_all_path: '/teams' }} /></MemoryRouter>)
    expect(screen.getByText('No teams are currently in your scope.')).toBeVisible()
  })
})
