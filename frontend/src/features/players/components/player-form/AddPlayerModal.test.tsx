// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClientError } from '@shared/api/client'
import { createPlayer } from '@features/players/api/playerApi'
import AddPlayerModal from '@features/players/components/player-form/AddPlayerModal'
import type { PlayerResponse } from '@features/players/types/player'

vi.mock('@features/players/api/playerApi', () => ({
  createPlayer: vi.fn(),
}))

const createdPlayer: PlayerResponse = {
  id: 'player-2',
  first_name: 'Maya',
  last_name: 'Patel',
  date_of_birth: '2009-06-12',
  bio: null,
  batting_style: 'left',
  bowling_style: 'left-arm orthodox',
  player_type: 'all-rounder',
  player_metadata: {},
  is_active: true,
  created_at: '2026-07-22T12:00:00Z',
  updated_at: '2026-07-22T12:00:00Z',
  version_number: 1,
  teams: [],
}

function fillRequiredFields() {
  fireEvent.change(screen.getByRole('textbox', { name: 'First name' }), {
    target: { value: 'Maya' },
  })
  fireEvent.change(screen.getByRole('textbox', { name: 'Last name' }), {
    target: { value: 'Patel' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Date of birth' }))
  fireEvent.change(screen.getByRole('combobox', { name: 'Year' }), {
    target: { value: '2009' },
  })
  fireEvent.change(screen.getByRole('combobox', { name: 'Month' }), {
    target: { value: '6' },
  })
  fireEvent.click(
    screen.getByRole('gridcell', {
      name: 'Friday, June 12, 2009',
    }),
  )
  fireEvent.change(screen.getByRole('combobox', { name: 'Batting style' }), {
    target: { value: 'left' },
  })
  fireEvent.change(screen.getByRole('combobox', { name: 'Bowling style' }), {
    target: { value: 'left-arm orthodox' },
  })
  fireEvent.change(screen.getByRole('combobox', { name: 'Player type' }), {
    target: { value: 'all-rounder' },
  })
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.restoreAllMocks()
  document.body.style.overflow = ''
})

describe('AddPlayerModal', () => {
  it('opens from an Add Player button, posts, closes, and reports the created player', async () => {
    vi.mocked(createPlayer).mockResolvedValue(createdPlayer)
    const onCreated = vi.fn()

    function Harness() {
      const [isOpen, setIsOpen] = useState(false)
      return (
        <>
          <button type="button" onClick={() => setIsOpen(true)}>
            Add Player
          </button>
          {isOpen ? (
            <AddPlayerModal
              onClose={() => setIsOpen(false)}
              onCreated={onCreated}
            />
          ) : null}
        </>
      )
    }

    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: 'Add Player' }))
    expect(screen.getByRole('dialog', { name: 'Add player' })).toBeVisible()

    fillRequiredFields()
    const submittedAt = performance.now()
    fireEvent.click(screen.getByRole('button', { name: 'Create player' }))

    await waitFor(
      () => expect(createPlayer).toHaveBeenCalledTimes(1),
      { timeout: 500 },
    )
    expect(onCreated).toHaveBeenCalledWith(createdPlayer)
    expect(performance.now() - submittedAt).toBeLessThan(500)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('disables submit within 500ms while creation is pending', () => {
    vi.mocked(createPlayer).mockReturnValue(new Promise(() => {}))
    render(<AddPlayerModal onClose={vi.fn()} onCreated={vi.fn()} />)
    fillRequiredFields()

    const submittedAt = performance.now()
    fireEvent.click(screen.getByRole('button', { name: 'Create player' }))

    expect(
      screen.getByRole('button', { name: 'Creating player…' }),
    ).toBeDisabled()
    expect(performance.now() - submittedAt).toBeLessThan(500)
  })

  it('keeps validation errors in the form without posting', () => {
    render(<AddPlayerModal onClose={vi.fn()} onCreated={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: 'Create player' }))

    expect(screen.getByText('Enter a first name.')).toBeVisible()
    expect(screen.getByRole('dialog')).toBeVisible()
    expect(createPlayer).not.toHaveBeenCalled()
  })

  it('shows a safe generic server error and leaves the modal open', async () => {
    vi.mocked(createPlayer).mockRejectedValue(new Error('database host leaked'))
    render(<AddPlayerModal onClose={vi.fn()} onCreated={vi.fn()} />)
    fillRequiredFields()

    const submittedAt = performance.now()
    fireEvent.click(screen.getByRole('button', { name: 'Create player' }))

    expect(
      await screen.findByRole('alert', {}, { timeout: 500 }),
    ).toHaveTextContent(
      'Unable to create player. Please try again.',
    )
    expect(performance.now() - submittedAt).toBeLessThan(500)
    expect(screen.queryByText(/database host leaked/i)).not.toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeVisible()
  })

  it('shows a clear permissions message for HTTP 403', async () => {
    vi.mocked(createPlayer).mockRejectedValue(
      new ApiClientError(403, { detail: 'raw forbidden detail' }),
    )
    render(<AddPlayerModal onClose={vi.fn()} onCreated={vi.fn()} />)
    fillRequiredFields()

    fireEvent.click(screen.getByRole('button', { name: 'Create player' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'You do not have permission to add players.',
    )
    expect(screen.queryByText(/raw forbidden/i)).not.toBeInTheDocument()
  })

  it('guards Escape and backdrop closing when the form is dirty', () => {
    const onClose = vi.fn()
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<AddPlayerModal onClose={onClose} onCreated={vi.fn()} />)
    fireEvent.change(screen.getByRole('textbox', { name: 'First name' }), {
      target: { value: 'Maya' },
    })

    fireEvent.keyDown(document, { key: 'Escape' })
    const backdrop = screen.getByTestId('add-player-backdrop')
    fireEvent.pointerDown(backdrop, { pointerId: 1 })
    fireEvent.pointerUp(backdrop, { pointerId: 1 })

    expect(confirm).toHaveBeenCalledTimes(2)
    expect(onClose).not.toHaveBeenCalled()
  })
})
