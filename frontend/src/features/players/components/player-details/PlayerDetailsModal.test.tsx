// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PlayerCard from '@features/players/components/player-directory/PlayerCard'
import PlayerDetailsModal from '@features/players/components/player-details/PlayerDetailsModal'
import type { PlayerResponse } from '@features/players/types/player'

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
  it('follows the shared player hierarchy without metadata or placeholders', () => {
    render(<PlayerDetailsModal player={player} onClose={vi.fn()} />)

    expect(screen.getByRole('dialog', { name: 'Asha Singh' })).toBeVisible()
    expect(
      screen.getByRole('heading', { name: 'Asha Singh', level: 2 }),
    ).toHaveAttribute('id', 'player-details-title')
    expect(
      screen.getByRole('heading', { name: 'Playing profile', level: 3 }),
    ).toBeVisible()
    expect(
      screen.getByRole('heading', { name: 'Biography', level: 3 }),
    ).toBeVisible()
    expect(screen.getByText('AS')).toHaveAttribute('aria-hidden', 'true')
    expect(screen.getByText('Junior XI, Development XI')).toBeVisible()
    expect(screen.getByText('All-Rounder')).toBeVisible()
    expect(
      screen.getByText(
        'Batting: Right-Handed · Bowling: Right-Arm Medium',
      ),
    ).toBeVisible()
    expect(screen.getByText('24 Apr 2008')).toBeVisible()
    expect(screen.getAllByText(/Right-Handed/)).toHaveLength(2)
    expect(screen.getAllByText(/Right-Arm Medium/)).toHaveLength(2)
    expect(screen.getByText('Opening batter')).toBeVisible()
    expect(screen.queryByText(/statistics deferred/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/squad_number/i)).not.toBeInTheDocument()
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
    const backdrop = screen.getByTestId('player-details-backdrop')
    fireEvent.pointerDown(backdrop, { pointerId: 1 })
    fireEvent.pointerUp(backdrop, { pointerId: 1 })
    expect(onClose).toHaveBeenCalledTimes(3)
  })

  it('shows the Edit Player control only when editing is available', () => {
    const onEdit = vi.fn()
    const { rerender } = render(
      <PlayerDetailsModal
        player={player}
        onClose={vi.fn()}
        onEdit={onEdit}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Edit Player' }))
    expect(onEdit).toHaveBeenCalledTimes(1)

    rerender(<PlayerDetailsModal player={player} onClose={vi.fn()} />)
    expect(
      screen.queryByRole('button', { name: 'Edit Player' }),
    ).not.toBeInTheDocument()
  })

  it('traps keyboard focus inside the modal', () => {
    render(
      <PlayerDetailsModal
        player={player}
        onClose={vi.fn()}
        onEdit={vi.fn()}
      />,
    )
    const close = screen.getByRole('button', { name: 'Close player details' })
    const edit = screen.getByRole('button', { name: 'Edit Player' })
    expect(close).toHaveFocus()

    fireEvent.keyDown(document, { key: 'Tab' })
    expect(edit).toHaveFocus()
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
    expect(close).toHaveFocus()
  })

  it('shows biography directly when present', () => {
    render(<PlayerDetailsModal player={player} onClose={vi.fn()} />)

    expect(screen.getByRole('heading', { name: 'Biography' })).toBeVisible()
    expect(screen.getByText('Opening batter')).toBeVisible()
  })

  it('omits biography when it is absent', () => {
    render(
      <PlayerDetailsModal
        player={{ ...player, bio: null, player_metadata: {} }}
        onClose={vi.fn()}
      />,
    )

    expect(
      screen.queryByRole('heading', { name: 'Biography' }),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/no bio/i)).not.toBeInTheDocument()
  })
})
