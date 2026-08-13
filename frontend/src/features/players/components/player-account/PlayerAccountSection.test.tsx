// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PlayerAccountSection from './PlayerAccountSection'
import * as playerApi from '../../api/playerApi'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('PlayerAccountSection', () => {
  it('shows only the safe linked-account snapshot to a Head Coach', async () => {
    vi.spyOn(playerApi, 'fetchPlayerAccountAssociation').mockResolvedValue({
      player_id: 'player-1',
      player_version_number: 3,
      account: {
        id: 'account-1',
        display_name: 'Rohan Account',
        email: 'rohan@example.com',
        role: 'player',
        is_active: true,
      },
    })

    render(
      <PlayerAccountSection
        canManage
        playerId="player-1"
        versionNumber={3}
        onAssociationChanged={vi.fn()}
      />,
    )

    expect(await screen.findByText('Rohan Account')).toBeVisible()
    expect(screen.getByText('rohan@example.com')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Reassign account' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Unlink account' })).toBeVisible()
    expect(screen.queryByText(/password|session|token/i)).not.toBeInTheDocument()
  })

  it('shows the unlinked state and keeps controls hidden when forbidden', async () => {
    vi.spyOn(playerApi, 'fetchPlayerAccountAssociation').mockResolvedValue({
      player_id: 'player-1',
      player_version_number: 2,
      account: null,
    })

    const { rerender } = render(
      <PlayerAccountSection
        canManage
        playerId="player-1"
        versionNumber={2}
        onAssociationChanged={vi.fn()}
      />,
    )

    expect(await screen.findByText('No account linked')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Link account' })).toBeVisible()

    rerender(
      <PlayerAccountSection
        canManage={false}
        playerId="player-1"
        versionNumber={2}
        onAssociationChanged={vi.fn()}
      />,
    )
    expect(screen.queryByRole('button', { name: 'Link account' })).not.toBeInTheDocument()
  })

  it('reloads the protected association after a conflict', async () => {
    const fetchAssociation = vi
      .spyOn(playerApi, 'fetchPlayerAccountAssociation')
      .mockRejectedValueOnce(new Error('temporary'))
      .mockResolvedValueOnce({
        player_id: 'player-1',
        player_version_number: 4,
        account: null,
      })

    render(
      <PlayerAccountSection
        canManage
        playerId="player-1"
        versionNumber={3}
        onAssociationChanged={vi.fn()}
      />,
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to load the linked account',
    )
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))

    await waitFor(() => expect(fetchAssociation).toHaveBeenCalledTimes(2))
    expect(await screen.findByText('No account linked')).toBeVisible()
  })
})
