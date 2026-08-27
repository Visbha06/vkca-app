// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import RecentAcademyActivity from './RecentAcademyActivity'

describe('RecentAcademyActivity', () => {
  it('renders at most four recent activity rows and the permitted audit navigation', () => {
    const events = Array.from({ length: 4 }, (_, index) => ({
      id: `00000000-0000-4000-8000-00000000000${index}`,
      actor_display_name: 'Asha Coach',
      action_type: 'player.created' as const,
      action_category: 'player' as const,
      target_label: `Player ${index}`,
      summary: `Asha Coach added Player ${index}`,
      created_at: '2026-08-10T18:00:00Z',
    }))
    render(<MemoryRouter><RecentAcademyActivity context={{ kind: 'recent_activity', events, view_all_path: '/audit-log' }} /></MemoryRouter>)

    expect(screen.getAllByRole('listitem')).toHaveLength(4)
    expect(screen.getByRole('link', { name: 'View all activity' })).toHaveAttribute('href', '/audit-log')
  })

  it('renders compact activity dates in the academy timezone', () => {
    const event = {
      id: '00000000-0000-4000-8000-000000000001',
      actor_display_name: 'Asha Coach',
      action_type: 'player.created' as const,
      action_category: 'player' as const,
      target_label: 'Rohan Player',
      summary: 'Asha Coach added Rohan Player',
      created_at: '2026-01-01T07:30:00Z',
    }

    render(
      <MemoryRouter>
        <RecentAcademyActivity
          context={{ kind: 'recent_activity', events: [event], view_all_path: '/audit-log' }}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('Dec 31')).toHaveAttribute(
      'datetime',
      event.created_at,
    )
  })
})
