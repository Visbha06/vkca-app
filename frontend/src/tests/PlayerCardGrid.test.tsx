// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PlayerCardGrid from '../components/PlayerCardGrid'
import type { PlayerResponse } from '../types/player'

const player: PlayerResponse = {
  id: 'player-1',
  first_name: 'Asha',
  last_name: 'Singh',
  date_of_birth: '2008-04-24',
  bio: null,
  batting_style: 'right',
  bowling_style: 'right-arm medium',
  player_type: 'all-rounder',
  player_metadata: {},
  is_active: true,
  created_at: '2026-07-01T10:00:00Z',
  updated_at: '2026-07-15T10:00:00Z',
  version_number: 1,
  teams: [{ id: 'team-1', name: 'Junior XI' }],
}

afterEach(cleanup)

describe('PlayerCardGrid', () => {
  it('renders players in a responsive grid', () => {
    render(
      <PlayerCardGrid
        players={[player, { ...player, id: 'player-2', first_name: 'Ravi' }]}
        isLoading={false}
        onSelect={vi.fn()}
      />,
    )

    const grid = screen.getByRole('list', { name: 'Players' })
    expect(grid).toHaveClass('grid-cols-1', 'sm:grid-cols-2', 'xl:grid-cols-3')
    expect(within(grid).getAllByRole('listitem')).toHaveLength(2)
  })

  it('shows an accessible loading state', () => {
    render(
      <PlayerCardGrid players={[]} isLoading onSelect={vi.fn()} />,
    )

    expect(screen.getByRole('status')).toHaveTextContent('Loading players')
  })

  it('shows the supplied empty state', () => {
    render(
      <PlayerCardGrid
        players={[]}
        isLoading={false}
        emptyMessage="No active players are available."
        onSelect={vi.fn()}
      />,
    )

    expect(screen.getByText('No active players are available.')).toBeVisible()
  })
})
