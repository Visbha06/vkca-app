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
import { createCoach } from '../../api/coachApi'
import { fetchTeams } from '@features/teams/api/teamApi'
import AddCoachModal from './AddCoachModal'
import type { CoachCreateResponse } from '../../types/coach'

vi.mock('../../api/coachApi', () => ({
  createCoach: vi.fn(),
}))

vi.mock('@features/teams/api/teamApi', () => ({
  fetchTeams: vi.fn(),
}))

const createdCoach: CoachCreateResponse = {
  id: 'coach-2',
  first_name: 'Asha',
  last_name: 'Patel',
  email: 'asha@vkca.test',
  role: 'assistant coach',
  is_active: true,
  version_number: 1,
  created_at: '2026-07-29T10:00:00Z',
  updated_at: '2026-07-29T10:00:00Z',
  teams: [{ id: 'team-1', name: 'U13 Lions' }],
  temporary_password: 'Aa1!temporary-token',
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

function renderModal(
  onClose = vi.fn(),
  onCreated = vi.fn(),
) {
  vi.mocked(fetchTeams).mockResolvedValue({
    teams: [
      {
        id: 'team-1',
        name: 'U13 Lions',
        age_group: 'U13',
        player_count: 11,
        created_at: '',
        updated_at: '',
        version_number: 1,
      },
    ],
    page: 1,
    page_size: 100,
    total_teams: 1,
    total_pages: 1,
  })
  render(<AddCoachModal onClose={onClose} onCreated={onCreated} />)
  return { onClose, onCreated }
}

function completeRequiredFields() {
  fireEvent.change(screen.getByLabelText('First name'), {
    target: { value: 'Asha' },
  })
  fireEvent.change(screen.getByLabelText('Last name'), {
    target: { value: 'Patel' },
  })
  fireEvent.change(screen.getByLabelText('Email address'), {
    target: { value: 'asha@vkca.test' },
  })
}

describe('AddCoachModal', () => {
  it('renders the form and reports field-level validation errors', () => {
    renderModal()

    fireEvent.click(screen.getByRole('button', { name: 'Create coach' }))

    expect(screen.getByText('Enter a first name.')).toBeVisible()
    expect(screen.getByText('Enter a last name.')).toBeVisible()
    expect(screen.getByText('Enter an email address.')).toBeVisible()
    expect(createCoach).not.toHaveBeenCalled()
  })

  it('creates a coach, displays the password once, and copies it', async () => {
    const clipboard = { writeText: vi.fn().mockResolvedValue(undefined) }
    vi.stubGlobal('navigator', { clipboard })
    vi.mocked(createCoach).mockResolvedValue(createdCoach)
    const { onCreated } = renderModal()

    completeRequiredFields()
    fireEvent.click(
      await screen.findByRole('checkbox', { name: /U13 Lions/ }),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Create coach' }))

    expect(
      await screen.findByText('This password will only be shown once'),
    ).toBeVisible()
    expect(screen.getByDisplayValue('Aa1!temporary-token')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Copy password' }))
    await waitFor(() =>
      expect(clipboard.writeText).toHaveBeenCalledWith(
        'Aa1!temporary-token',
      ),
    )
    expect(await screen.findByText('Password copied')).toBeVisible()
    const { temporary_password, ...coach } = createdCoach
    expect(temporary_password).toBe('Aa1!temporary-token')
    expect(onCreated).toHaveBeenCalledWith(coach)
  })

  it('preserves form data and shows duplicate email as a field error', async () => {
    vi.mocked(createCoach).mockRejectedValue(
      new ApiClientError(409, {
        detail: "A user with email 'asha@vkca.test' already exists.",
      }),
    )
    renderModal()

    completeRequiredFields()
    fireEvent.click(screen.getByRole('button', { name: 'Create coach' }))

    expect(
      await screen.findByText('An account with this email already exists.'),
    ).toBeVisible()
    expect(screen.getByLabelText('First name')).toHaveValue('Asha')
    expect(
      screen.getByRole('textbox', { name: /Email address/ }),
    ).toHaveValue('asha@vkca.test')
  })

  it('confirms before discarding an edited form', () => {
    const confirm = vi.fn().mockReturnValue(false)
    vi.stubGlobal('confirm', confirm)
    const { onClose } = renderModal()

    fireEvent.change(screen.getByLabelText('First name'), {
      target: { value: 'Asha' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Close add coach' }))

    expect(confirm).toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
  })
})
