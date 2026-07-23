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
    const informationToggle = screen.getByRole('button', {
      name: 'Show bio and metadata',
    })
    expect(close).toHaveFocus()

    fireEvent.keyDown(document, { key: 'Tab' })
    expect(informationToggle).toHaveFocus()
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
    expect(close).toHaveFocus()
  })

  it('expands and collapses the player bio and metadata', () => {
    const playerWithMetadata: PlayerResponse = {
      ...player,
      player_metadata: {
        squad_number: 12,
        availability: true,
      },
    }

    render(<PlayerDetailsModal player={playerWithMetadata} onClose={vi.fn()} />)
    const toggle = screen.getByRole('button', { name: 'Show bio and metadata' })

    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Opening batter')).not.toBeInTheDocument()

    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Opening batter')).toBeVisible()
    expect(screen.getByText('squad_number')).toBeVisible()
    expect(screen.getByText('12')).toBeVisible()
    expect(screen.getByText('availability')).toBeVisible()
    expect(screen.getByText('true')).toBeVisible()

    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Opening batter')).not.toBeInTheDocument()
  })

  it('shows an empty message when bio and metadata are absent', () => {
    render(
      <PlayerDetailsModal
        player={{ ...player, bio: null, player_metadata: {} }}
        onClose={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Show bio and metadata' }))

    expect(
      screen.getByText('No bio or additional player information has been added.'),
    ).toBeVisible()
  })

  it('serializes nested metadata values for readable display', () => {
    render(
      <PlayerDetailsModal
        player={{
          ...player,
          player_metadata: {
            preferences: { position: 'opener', overs: [1, 3, 5] },
          },
        }}
        onClose={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Show bio and metadata' }))

    expect(screen.getByText('preferences')).toBeVisible()
    expect(
      screen.getByText('{"position":"opener","overs":[1,3,5]}'),
    ).toBeVisible()
  })

  it('renders metadata keys and values as text rather than HTML', () => {
    const unsafeMarkup = '<img src=x onerror="alert(1)">'
    const { container } = render(
      <PlayerDetailsModal
        player={{
          ...player,
          bio: null,
          player_metadata: { [unsafeMarkup]: unsafeMarkup },
        }}
        onClose={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Show bio and metadata' }))

    expect(screen.getAllByText(unsafeMarkup)).toHaveLength(2)
    expect(container.querySelector('img')).not.toBeInTheDocument()
  })
})
