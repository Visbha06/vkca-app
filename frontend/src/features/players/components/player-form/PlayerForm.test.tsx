// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PlayerForm from '@features/players/components/player-form/PlayerForm'
import { PLAYER_BIO_MAX_LENGTH } from '@features/players/playerResourceLimits'

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
  vi.restoreAllMocks()
})

describe('PlayerForm', () => {
  it('shows field-level errors and does not submit missing required fields', () => {
    const onSubmit = vi.fn()
    render(<PlayerForm onSubmit={onSubmit} onCancel={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: 'Create player' }))

    expect(screen.getByText('Enter a first name.')).toBeVisible()
    expect(screen.getByText('Enter a last name.')).toBeVisible()
    expect(screen.getByText('Choose a date of birth.')).toBeVisible()
    expect(screen.getByText('Choose a batting style.')).toBeVisible()
    expect(screen.getByText('Choose a bowling style.')).toBeVisible()
    expect(screen.getByText('Choose a player type.')).toBeVisible()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('renders the custom date picker and enum controls, then submits API values', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<PlayerForm onSubmit={onSubmit} onCancel={vi.fn()} />)

    expect(
      screen.getByRole('button', { name: 'Date of birth' }),
    ).toHaveTextContent('Select date of birth')
    expect(
      screen.getByRole('option', { name: 'Right-Arm Fast' }),
    ).toHaveValue('right-arm fast')
    expect(
      screen.getByRole('option', { name: 'All-Rounder' }),
    ).toHaveValue('all-rounder')

    fillRequiredFields()
    fireEvent.change(screen.getByRole('textbox', { name: /^Bio/ }), {
      target: { value: '  Developing spin bowler.  ' },
    })
    fireEvent.change(screen.getByRole('textbox', { name: 'Metadata key 1' }), {
      target: { value: 'preferred_position' },
    })
    fireEvent.change(screen.getByRole('textbox', { name: 'Metadata value 1' }), {
      target: { value: 'middle order' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add metadata field' }))
    fireEvent.change(screen.getByRole('textbox', { name: 'Metadata key 2' }), {
      target: { value: 'shirt_number' },
    })
    fireEvent.change(screen.getByRole('textbox', { name: 'Metadata value 2' }), {
      target: { value: '18' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create player' }))

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith({
        first_name: 'Maya',
        last_name: 'Patel',
        date_of_birth: '2009-06-12',
        bio: 'Developing spin bowler.',
        batting_style: 'left',
        bowling_style: 'left-arm orthodox',
        player_type: 'all-rounder',
        player_metadata: {
          preferred_position: 'middle order',
          shirt_number: '18',
        },
      }),
    )
  })

  it('validates metadata rows and prevents duplicate keys', () => {
    const onSubmit = vi.fn()
    render(<PlayerForm onSubmit={onSubmit} onCancel={vi.fn()} />)
    fillRequiredFields()

    fireEvent.change(screen.getByRole('textbox', { name: 'Metadata value 1' }), {
      target: { value: 'opener' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create player' }))
    expect(screen.getByText('Enter a key for this metadata value.')).toBeVisible()

    fireEvent.change(screen.getByRole('textbox', { name: 'Metadata key 1' }), {
      target: { value: 'position' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add metadata field' }))
    fireEvent.change(screen.getByRole('textbox', { name: 'Metadata key 2' }), {
      target: { value: 'position' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create player' }))

    expect(screen.getByText('Metadata keys must be unique.')).toBeVisible()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('exposes and enforces the biography length limit', () => {
    const onSubmit = vi.fn()
    render(<PlayerForm onSubmit={onSubmit} onCancel={vi.fn()} />)
    fillRequiredFields()
    const bio = screen.getByRole('textbox', { name: /^Bio/ })

    expect(bio).toHaveAttribute('maxlength', String(PLAYER_BIO_MAX_LENGTH))
    fireEvent.change(bio, {
      target: { value: 'x'.repeat(PLAYER_BIO_MAX_LENGTH + 1) },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create player' }))

    expect(
      screen.getByText('Keep the biography to 2,000 characters or fewer.'),
    ).toBeVisible()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('disables controls and communicates submission progress', () => {
    render(
      <PlayerForm
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
        isSubmitting
      />,
    )

    expect(
      screen.getByRole('button', { name: 'Creating player…' }),
    ).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent('Creating player')
    expect(screen.getByRole('textbox', { name: 'First name' })).toBeDisabled()
  })

  it('disables submit immediately when a valid submission starts', () => {
    function Harness() {
      const [isSubmitting, setIsSubmitting] = useState(false)
      return (
        <PlayerForm
          onSubmit={() => setIsSubmitting(true)}
          onCancel={vi.fn()}
          isSubmitting={isSubmitting}
        />
      )
    }

    render(<Harness />)
    fillRequiredFields()
    const startedAt = performance.now()
    fireEvent.click(screen.getByRole('button', { name: 'Create player' }))

    expect(
      screen.getByRole('button', { name: 'Creating player…' }),
    ).toBeDisabled()
    expect(performance.now() - startedAt).toBeLessThan(500)
  })

  it('shows server feedback accessibly', () => {
    render(
      <PlayerForm
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
        errorMessage="Unable to create player. Please try again."
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Unable to create player. Please try again.',
    )
  })

  it('shows permission feedback accessibly without exposing raw details', () => {
    render(
      <PlayerForm
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
        errorMessage="You do not have permission to add players."
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent(
      'You do not have permission to add players.',
    )
    expect(screen.queryByText(/raw forbidden detail/i)).not.toBeInTheDocument()
  })

  it('prompts before discarding unsaved changes', () => {
    const onCancel = vi.fn()
    const confirm = vi.spyOn(window, 'confirm')
    render(<PlayerForm onSubmit={vi.fn()} onCancel={onCancel} />)

    fireEvent.change(screen.getByRole('textbox', { name: 'First name' }), {
      target: { value: 'Maya' },
    })
    confirm.mockReturnValueOnce(false)
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onCancel).not.toHaveBeenCalled()

    confirm.mockReturnValueOnce(true)
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})
