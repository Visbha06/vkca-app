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
import {
  deactivateCoach,
  fetchCoachDetails,
  reactivateCoach,
} from '../../api/coachApi'
import CoachDetailsModal from './CoachDetailsModal'
import type { CoachResponse } from '../../types/coach'

vi.mock('../../api/coachApi', () => ({
  deactivateCoach: vi.fn(),
  fetchCoachDetails: vi.fn(),
  reactivateCoach: vi.fn(),
}))

const coach: CoachResponse = {
  id: 'coach-1',
  first_name: 'Vikram',
  last_name: 'Kumar',
  email: 'vikram@vkca.test',
  role: 'head coach',
  is_active: true,
  version_number: 1,
  created_at: '2026-07-01T10:00:00Z',
  updated_at: '2026-07-15T10:00:00Z',
  teams: [{ id: 'team-1', name: 'U13 Lions' }],
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  document.body.style.overflow = ''
})

describe('CoachDetailsModal', () => {
  it('renders coach details, assigned teams, and fixed placeholder statistics', () => {
    render(
      <CoachDetailsModal
        coach={coach}
        currentUserId="head-2"
        currentUserRole="head coach"
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByRole('dialog', { name: 'Vikram Kumar' })).toBeVisible()
    expect(screen.getByText('vikram@vkca.test')).toBeVisible()
    expect(screen.getByText('Head Coach')).toBeVisible()
    expect(screen.getByText('Active')).toBeVisible()
    expect(screen.getByText('U13 Lions')).toBeVisible()
    expect(screen.getByText('Availability for next practice')).toBeVisible()
    expect(screen.getByText('Not available')).toBeVisible()
    expect(screen.getByText('Notes made')).toBeVisible()
    expect(screen.getByText('0')).toBeVisible()
  })

  it('keeps management controls unavailable to Assistant Coaches', () => {
    render(
      <CoachDetailsModal
        coach={{ ...coach, teams: [] }}
        currentUserId="assistant-1"
        currentUserRole="assistant coach"
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByText('No teams assigned')).toBeVisible()
    expect(screen.queryByText('Head Coach controls')).not.toBeInTheDocument()
  })

  it('closes with Escape and the close control while trapping focus', () => {
    const onClose = vi.fn()
    render(
      <CoachDetailsModal
        coach={coach}
        currentUserId="head-2"
        currentUserRole="head coach"
        onClose={onClose}
      />,
    )
    const close = screen.getByRole('button', { name: 'Close coach details' })

    expect(document.body.style.overflow).toBe('hidden')
    expect(close).toHaveFocus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(
      screen.getByRole('button', { name: 'Deactivate coach' }),
    ).toHaveFocus()
    fireEvent.keyDown(document, { key: 'Escape' })
    fireEvent.click(close)
    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it('applies a successful status update immediately', async () => {
    const onCoachUpdated = vi.fn()
    vi.mocked(deactivateCoach).mockResolvedValue({
      id: coach.id,
      first_name: coach.first_name,
      last_name: coach.last_name,
      email: coach.email,
      role: coach.role,
      is_active: false,
      version_number: 2,
      created_at: coach.created_at,
      updated_at: coach.updated_at,
    })
    render(
      <CoachDetailsModal
        coach={coach}
        currentUserId="head-2"
        currentUserRole="head coach"
        onClose={vi.fn()}
        onCoachUpdated={onCoachUpdated}
      />,
    )

    fireEvent.click(
      screen.getByRole('button', { name: 'Deactivate coach' }),
    )
    fireEvent.click(
      screen.getByRole('button', { name: 'Confirm deactivation' }),
    )

    expect(await screen.findByText('Inactive')).toBeVisible()
    expect(deactivateCoach).toHaveBeenCalledWith(coach.id, 1)
    expect(onCoachUpdated).toHaveBeenCalledWith({
      ...coach,
      is_active: false,
      version_number: 2,
    })
  })

  it('updates status and offers reload after an OCC conflict', async () => {
    const onCoachUpdated = vi.fn()
    const onCoachReloaded = vi.fn()
    vi.mocked(deactivateCoach).mockRejectedValue(
      new ApiClientError(409, {
        detail: 'Stale version 1 for users entity coach-1.',
      }),
    )
    vi.mocked(fetchCoachDetails).mockResolvedValue({
      ...coach,
      version_number: 2,
    })
    render(
      <CoachDetailsModal
        coach={coach}
        currentUserId="head-2"
        currentUserRole="head coach"
        onClose={vi.fn()}
        onCoachUpdated={onCoachUpdated}
        onCoachReloaded={onCoachReloaded}
      />,
    )

    fireEvent.click(
      screen.getByRole('button', { name: 'Deactivate coach' }),
    )
    fireEvent.click(
      screen.getByRole('button', { name: 'Confirm deactivation' }),
    )
    expect(
      await screen.findByText(/updated by another user/i),
    ).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Reload' }))
    await waitFor(() =>
      expect(fetchCoachDetails).toHaveBeenCalledWith(coach.id),
    )
    expect(onCoachReloaded).toHaveBeenCalledWith({
      ...coach,
      version_number: 2,
    })
    expect(onCoachUpdated).not.toHaveBeenCalled()
    expect(reactivateCoach).not.toHaveBeenCalled()
  })
})
