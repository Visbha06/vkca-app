// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClientError } from '@shared/api/client'
import PlayerAccountLinkDialog from './PlayerAccountLinkDialog'
import * as playerApi from '../../api/playerApi'

const eligible = {
  users: [
    {
      id: 'account-1',
      display_name: 'Rohan Account',
      email: 'rohan@example.com',
      role: 'player' as const,
      is_active: true,
    },
  ],
  page: 1,
  page_size: 20,
  total_users: 1,
  total_pages: 1,
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function renderLinkDialog(onClose = vi.fn()) {
  vi.spyOn(playerApi, 'fetchEligiblePlayerAccounts').mockResolvedValue(eligible)
  const onSaved = vi.fn()
  return {
    onClose,
    onSaved,
    ...render(
      <PlayerAccountLinkDialog
        mode="link"
        playerId="player-1"
        versionNumber={1}
        currentAccount={null}
        onClose={onClose}
        onConflict={vi.fn()}
        onSaved={onSaved}
      />,
    ),
  }
}

describe('PlayerAccountLinkDialog', () => {
  it('dismisses a clean dialog normally without a warning', async () => {
    const onClose = vi.fn()
    renderLinkDialog(onClose)

    await screen.findByRole('heading', { name: 'Link player account' })
    fireEvent.click(screen.getByRole('button', { name: 'Close account linking' }))

    expect(onClose).toHaveBeenCalledTimes(1)
    expect(screen.queryByText('Discard unsaved changes?')).not.toBeInTheDocument()
  })

  it('intercepts dirty close and preserves values on Continue editing', async () => {
    const onClose = vi.fn()
    renderLinkDialog(onClose)
    const search = await screen.findByRole('searchbox', { name: 'Search player accounts' })
    fireEvent.change(search, { target: { value: 'Rohan' } })
    fireEvent.click(screen.getByRole('radio', { name: /Rohan Account/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Close account linking' }))

    expect(screen.getByRole('heading', { name: 'Discard unsaved changes?' })).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Continue editing' }))

    expect(screen.getByRole('searchbox', { name: 'Search player accounts' })).toHaveValue('Rohan')
    expect(screen.getByRole('radio', { name: /Rohan Account/ })).toBeChecked()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('intercepts a permitted backdrop dismissal when dirty', async () => {
    renderLinkDialog()
    fireEvent.change(
      await screen.findByRole('searchbox', { name: 'Search player accounts' }),
      { target: { value: 'Rohan' } },
    )

    const backdrop = screen.getByTestId('player-account-dialog')
    fireEvent.pointerDown(backdrop, { pointerId: 7 })
    fireEvent.pointerUp(backdrop, { pointerId: 7 })

    expect(screen.getByRole('heading', { name: 'Discard unsaved changes?' })).toBeVisible()
  })

  it('discards dirty Escape dismissal without sending a mutation', async () => {
    const onClose = vi.fn()
    const save = vi.spyOn(playerApi, 'linkPlayerAccount')
    renderLinkDialog(onClose)
    const search = await screen.findByRole('searchbox', { name: 'Search player accounts' })
    fireEvent.change(search, { target: { value: 'Rohan' } })
    fireEvent.keyDown(document, { key: 'Escape' })

    fireEvent.click(await screen.findByRole('button', { name: 'Discard changes' }))

    expect(onClose).toHaveBeenCalledTimes(1)
    expect(save).not.toHaveBeenCalled()
  })

  it('requires an explicit account selection before linking', async () => {
    vi.spyOn(playerApi, 'fetchEligiblePlayerAccounts').mockResolvedValue(eligible)
    const link = vi.spyOn(playerApi, 'linkPlayerAccount').mockResolvedValue({
      player_id: 'player-1',
      player_version_number: 2,
      account: eligible.users[0],
    })
    const onSaved = vi.fn()
    render(
      <PlayerAccountLinkDialog
        mode="link"
        playerId="player-1"
        versionNumber={1}
        currentAccount={null}
        onClose={vi.fn()}
        onConflict={vi.fn()}
        onSaved={onSaved}
      />,
    )

    const confirm = await screen.findByRole('button', { name: 'Link selected account' })
    expect(confirm).toBeDisabled()
    fireEvent.click(screen.getByRole('radio', { name: /Rohan Account/ }))
    fireEvent.click(confirm)

    await waitFor(() =>
      expect(link).toHaveBeenCalledWith('player-1', {
        user_id: 'account-1',
        version_number: 1,
      }),
    )
    expect(onSaved).toHaveBeenCalled()
  })

  it('submits explicit unlink and reassignment confirmations', async () => {
    const currentAccount = eligible.users[0]
    const unlinked = {
      player_id: 'player-1',
      player_version_number: 4,
      account: null,
    }
    const unlink = vi
      .spyOn(playerApi, 'unlinkPlayerAccount')
      .mockResolvedValue(unlinked)
    const { unmount } = render(
      <PlayerAccountLinkDialog
        mode="unlink"
        playerId="player-1"
        versionNumber={3}
        currentAccount={currentAccount}
        onClose={vi.fn()}
        onConflict={vi.fn()}
        onSaved={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Unlink account' }))
    await waitFor(() =>
      expect(unlink).toHaveBeenCalledWith('player-1', { version_number: 3 }),
    )
    unmount()

    const replacement = {
      ...eligible,
      users: [{ ...eligible.users[0], id: 'account-2' }],
    }
    vi.spyOn(playerApi, 'fetchEligiblePlayerAccounts').mockResolvedValue(replacement)
    const reassign = vi
      .spyOn(playerApi, 'reassignPlayerAccount')
      .mockResolvedValue({
        player_id: 'player-1',
        player_version_number: 5,
        account: replacement.users[0],
      })
    render(
      <PlayerAccountLinkDialog
        mode="reassign"
        playerId="player-1"
        versionNumber={4}
        currentAccount={currentAccount}
        onClose={vi.fn()}
        onConflict={vi.fn()}
        onSaved={vi.fn()}
      />,
    )

    fireEvent.click(await screen.findByRole('radio', { name: /Rohan Account/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Reassign selected account' }))
    await waitFor(() =>
      expect(reassign).toHaveBeenCalledWith('player-1', {
        expected_user_id: 'account-1',
        new_user_id: 'account-2',
        version_number: 4,
      }),
    )
  })

  it('offers an explicit reload after a conflict without retrying the mutation', async () => {
    vi.spyOn(playerApi, 'fetchEligiblePlayerAccounts').mockResolvedValue(eligible)
    const link = vi
      .spyOn(playerApi, 'linkPlayerAccount')
      .mockRejectedValue(new ApiClientError(409, { detail: 'stale version' }))
    const onConflict = vi.fn()
    render(
      <PlayerAccountLinkDialog
        mode="link"
        playerId="player-1"
        versionNumber={1}
        currentAccount={null}
        onClose={vi.fn()}
        onConflict={onConflict}
        onSaved={vi.fn()}
      />,
    )

    fireEvent.click(await screen.findByRole('radio', { name: /Rohan Account/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Link selected account' }))
    fireEvent.click(
      await screen.findByRole('button', { name: 'Reload latest account link' }),
    )

    expect(onConflict).toHaveBeenCalledTimes(1)
    expect(link).toHaveBeenCalledTimes(1)
  })

  it('clears discarded state, restores focus, and performs no mutation', async () => {
    vi.spyOn(playerApi, 'fetchEligiblePlayerAccounts').mockResolvedValue(eligible)
    const link = vi.spyOn(playerApi, 'linkPlayerAccount')
    const unlink = vi.spyOn(playerApi, 'unlinkPlayerAccount')
    const reassign = vi.spyOn(playerApi, 'reassignPlayerAccount')

    function Harness() {
      const [open, setOpen] = useState(false)
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>Open account link</button>
          {open ? (
            <PlayerAccountLinkDialog
              mode="link"
              playerId="player-1"
              versionNumber={1}
              currentAccount={null}
              onClose={() => setOpen(false)}
              onConflict={vi.fn()}
              onSaved={vi.fn()}
            />
          ) : null}
        </>
      )
    }

    render(<Harness />)
    const trigger = screen.getByRole('button', { name: 'Open account link' })
    trigger.focus()
    fireEvent.click(trigger)
    fireEvent.change(
      await screen.findByRole('searchbox', { name: 'Search player accounts' }),
      { target: { value: 'Rohan' } },
    )
    fireEvent.keyDown(document, { key: 'Escape' })
    fireEvent.click(screen.getByRole('button', { name: 'Discard changes' }))

    await waitFor(() => expect(trigger).toHaveFocus())
    expect(screen.queryByTestId('player-account-dialog')).not.toBeInTheDocument()
    expect(link).not.toHaveBeenCalled()
    expect(unlink).not.toHaveBeenCalled()
    expect(reassign).not.toHaveBeenCalled()

    fireEvent.click(trigger)
    expect(
      await screen.findByRole('searchbox', { name: 'Search player accounts' }),
    ).toHaveValue('')
  })
})
