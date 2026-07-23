// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PlayerCard from '../components/PlayerCard'
import PlayerDetailsModal from '../components/PlayerDetailsModal'
import type { PlayerResponse } from '../types/player'

const player: PlayerResponse = {
  id: 'player-1',
  first_name: 'Asha',
  last_name: 'Singh',
  date_of_birth: '2008-04-24',
  bio: 'Opening batter',
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

afterEach(() => {
  cleanup()
  document.body.style.overflow = ''
})

describe('PlayerDetailsModal', () => {
  it('displays all Phase 3 player details and the statistics placeholder', () => {
    render(<PlayerDetailsModal player={player} onClose={vi.fn()} />)

    expect(screen.getByRole('dialog', { name: 'Asha Singh' })).toBeVisible()
    expect(screen.getByText('24 Apr 2008')).toBeVisible()
    expect(screen.getByText('Right-Handed')).toBeVisible()
    expect(screen.getByText('Right-Arm Medium')).toBeVisible()
    expect(screen.getByText('All-Rounder')).toBeVisible()
    expect(screen.getByText('Junior XI, Development XI')).toBeVisible()
    expect(
      screen.getByText('Player statistics deferred to a future specification.'),
    ).toBeVisible()
  })

  it('opens from a card and restores focus after closing', () => {
    function Harness() {
      const [open, setOpen] = useState(false)
      return (
        <>
          <PlayerCard player={player} onSelect={() => setOpen(true)} />
          {open ? (
            <PlayerDetailsModal player={player} onClose={() => setOpen(false)} />
          ) : null}
        </>
      )
    }

    render(<Harness />)
    const card = screen.getByRole('button', { name: /view asha singh/i })
    card.focus()
    fireEvent.click(card)
    expect(screen.getByRole('dialog', { name: 'Asha Singh' })).toBeVisible()

    fireEvent.click(screen.getByRole('button', { name: 'Close player details' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(card).toHaveFocus()
  })

  it('closes on Escape, the close button, and the backdrop', () => {
    const onClose = vi.fn()
    render(<PlayerDetailsModal player={player} onClose={onClose} />)

    fireEvent.keyDown(document, { key: 'Escape' })
    fireEvent.click(screen.getByRole('button', { name: 'Close player details' }))
    fireEvent.click(screen.getByTestId('player-details-backdrop'))
    expect(onClose).toHaveBeenCalledTimes(3)
  })

  it('traps keyboard focus inside the modal', () => {
    render(<PlayerDetailsModal player={player} onClose={vi.fn()} />)
    const close = screen.getByRole('button', { name: 'Close player details' })
    expect(close).toHaveFocus()

    fireEvent.keyDown(document, { key: 'Tab' })
    expect(close).toHaveFocus()
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
    expect(close).toHaveFocus()
  })
})
