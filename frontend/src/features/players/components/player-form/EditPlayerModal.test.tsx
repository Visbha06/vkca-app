// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClientError } from '@shared/api/client'
import { fetchPlayer, updatePlayer } from '@features/players/api/playerApi'
import EditPlayerModal from '@features/players/components/player-form/EditPlayerModal'
import type { PlayerResponse } from '@features/players/types/player'

vi.mock('@features/players/api/playerApi', () => ({
  fetchPlayer: vi.fn(),
  updatePlayer: vi.fn(),
}))

const player: PlayerResponse = {
  id: 'player-1',
  first_name: 'Asha',
  last_name: 'Singh',
  date_of_birth: '2008-04-24',
  bio: 'Opening batter',
  batting_style: 'right',
  bowling_style: 'right-arm medium',
  player_type: 'all-rounder',
  player_metadata: { squad_number: 12 },
  is_active: true,
  created_at: '2026-07-01T10:00:00Z',
  updated_at: '2026-07-15T10:00:00Z',
  version_number: 3,
  teams: [{ id: 'team-1', name: 'Junior XI' }],
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.restoreAllMocks()
  document.body.style.overflow = ''
})

describe('EditPlayerModal', () => {
  it('pre-fills player data with readable enum labels and date display', () => {
    render(
      <EditPlayerModal
        player={player}
        onClose={vi.fn()}
        onUpdated={vi.fn()}
      />,
    )

    expect(screen.getByRole('dialog', { name: 'Edit Asha Singh' })).toBeVisible()
    expect(screen.getByRole('textbox', { name: 'First name' })).toHaveValue(
      'Asha',
    )
    expect(screen.getByRole('textbox', { name: 'Last name' })).toHaveValue(
      'Singh',
    )
    expect(
      screen.getByRole('button', { name: 'Date of birth' }),
    ).toHaveTextContent('April 24, 2008')
    expect(screen.getByRole('combobox', { name: 'Batting style' })).toHaveValue(
      'right',
    )
    expect(
      screen.getByRole('option', { name: 'Right-Handed', selected: true }),
    ).toBeVisible()
    expect(screen.getByRole('combobox', { name: 'Bowling style' })).toHaveValue(
      'right-arm medium',
    )
    expect(
      screen.getByRole('option', {
        name: 'Right-Arm Medium',
        selected: true,
      }),
    ).toBeVisible()
    expect(screen.getByRole('combobox', { name: 'Player type' })).toHaveValue(
      'all-rounder',
    )
    expect(screen.getByRole('textbox', { name: 'Metadata key 1' })).toHaveValue(
      'squad_number',
    )
    expect(
      screen.getByRole('textbox', { name: 'Metadata value 1' }),
    ).toHaveValue('12')
  })

  it('submits updates with the current version and reports success', async () => {
    const updatedPlayer = {
      ...player,
      date_of_birth: '2008-04-25',
      bio: 'Opening batter and vice-captain',
      version_number: 4,
    }
    vi.mocked(updatePlayer).mockResolvedValue(updatedPlayer)
    const onUpdated = vi.fn()

    render(
      <EditPlayerModal
        player={player}
        onClose={vi.fn()}
        onUpdated={onUpdated}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Date of birth' }))
    fireEvent.click(
      screen.getByRole('gridcell', {
        name: 'Friday, April 25, 2008',
      }),
    )
    fireEvent.change(screen.getByRole('textbox', { name: /^Bio/ }), {
      target: { value: 'Opening batter and vice-captain' },
    })
    const submittedAt = performance.now()
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    await waitFor(
      () =>
        expect(updatePlayer).toHaveBeenCalledWith('player-1', {
          first_name: 'Asha',
          last_name: 'Singh',
          date_of_birth: '2008-04-25',
          bio: 'Opening batter and vice-captain',
          batting_style: 'right',
          bowling_style: 'right-arm medium',
          player_type: 'all-rounder',
          player_metadata: { squad_number: 12 },
          version_number: 3,
        }),
      { timeout: 500 },
    )
    expect(onUpdated).toHaveBeenCalledWith(updatedPlayer)
    expect(performance.now() - submittedAt).toBeLessThan(500)
  })

  it('handles a 409 conflict and reloads the latest player into the form', async () => {
    const latestPlayer = {
      ...player,
      first_name: 'Asha-Rae',
      bio: 'Updated by another coach',
      version_number: 4,
    }
    vi.mocked(updatePlayer).mockRejectedValue(
      new ApiClientError(409, { detail: 'Stale version 3' }),
    )
    vi.mocked(fetchPlayer).mockResolvedValue(latestPlayer)

    render(
      <EditPlayerModal
        player={player}
        onClose={vi.fn()}
        onUpdated={vi.fn()}
      />,
    )

    fireEvent.change(screen.getByRole('textbox', { name: 'First name' }), {
      target: { value: 'Local edit' },
    })
    const submittedAt = performance.now()
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    const alert = await screen.findByRole('alert', {}, { timeout: 500 })
    expect(alert).toHaveTextContent(
      'This player was updated by another user.',
    )
    expect(performance.now() - submittedAt).toBeLessThan(500)
    expect(alert).toHaveFocus()
    fireEvent.click(screen.getByRole('button', { name: 'Reload latest player' }))

    await waitFor(() => expect(fetchPlayer).toHaveBeenCalledWith('player-1'))
    expect(screen.getByRole('textbox', { name: 'First name' })).toHaveValue(
      'Asha-Rae',
    )
    expect(screen.getByRole('textbox', { name: /^Bio/ })).toHaveValue(
      'Updated by another coach',
    )
    expect(updatePlayer).toHaveBeenCalledTimes(1)
  })

  it('shows a clear permissions message for HTTP 403', async () => {
    vi.mocked(updatePlayer).mockRejectedValue(
      new ApiClientError(403, { detail: 'raw forbidden detail' }),
    )

    render(
      <EditPlayerModal
        player={player}
        onClose={vi.fn()}
        onUpdated={vi.fn()}
      />,
    )

    fireEvent.change(screen.getByRole('textbox', { name: 'First name' }), {
      target: { value: 'Asha-Rae' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'You do not have permission to edit players.',
    )
    expect(screen.queryByText(/raw forbidden detail/i)).not.toBeInTheDocument()
  })

  it('prompts before discarding unsaved changes from every close path', () => {
    const onClose = vi.fn()
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)

    render(
      <EditPlayerModal
        player={player}
        onClose={onClose}
        onUpdated={vi.fn()}
      />,
    )

    fireEvent.change(screen.getByRole('textbox', { name: 'First name' }), {
      target: { value: 'Asha-Rae' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    fireEvent.keyDown(document, { key: 'Escape' })
    fireEvent.click(screen.getByTestId('edit-player-backdrop'))

    expect(confirm).toHaveBeenCalledTimes(3)
    expect(onClose).not.toHaveBeenCalled()
  })
})
