// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PlayerCard from '@features/players/components/player-directory/PlayerCard'
import type { PlayerResponse } from '@features/players/types/player'

const assignedPlayer: PlayerResponse = {
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
  teams: [
    { id: 'team-1', name: 'Junior XI' },
    { id: 'team-2', name: 'Development XI' },
  ],
}

afterEach(cleanup)

describe('PlayerCard', () => {
  it('renders compact identity, stable team summary, playing profile, and date', () => {
    render(<PlayerCard player={assignedPlayer} onSelect={vi.fn()} />)

    expect(screen.getByRole('button', { name: /view asha singh/i })).toBeVisible()
    expect(screen.getByText('AS')).toHaveAttribute('aria-hidden', 'true')
    expect(screen.getByText('Junior XI +1 more')).toBeVisible()
    expect(screen.getByText('All-Rounder')).toBeVisible()
    expect(
      screen.getByText(
        'Bat: Right-Handed · Bowl: Right-Arm Medium',
      ),
    ).toBeVisible()
    expect(screen.getByText('Born 24 Apr 2008')).toBeVisible()
  })

  it('shows Unassigned when the player has no teams', () => {
    render(
      <PlayerCard
        player={{ ...assignedPlayer, teams: [] }}
        onSelect={vi.fn()}
      />,
    )

    expect(screen.getByText('Unassigned')).toBeVisible()
  })

  it('uses a native keyboard-focusable button and opens when activated', () => {
    const onSelect = vi.fn()
    render(<PlayerCard player={assignedPlayer} onSelect={onSelect} />)

    const card = screen.getByRole('button', { name: /view asha singh/i })
    card.focus()
    expect(card).toHaveFocus()
    expect(card.tagName).toBe('BUTTON')
    fireEvent.click(card)
    expect(onSelect).toHaveBeenCalledWith(assignedPlayer)
  })
})
