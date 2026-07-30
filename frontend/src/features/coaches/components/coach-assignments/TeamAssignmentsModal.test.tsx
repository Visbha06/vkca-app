// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchTeams } from '@features/teams/api/teamApi'
import { ApiClientError } from '@shared/api/client'
import { fetchCoachDetails, updateTeamAssignments } from '../../api/coachApi'
import type { CoachResponse } from '../../types/coach'
import TeamAssignmentsModal from './TeamAssignmentsModal'

vi.mock('@features/teams/api/teamApi', () => ({
  fetchTeams: vi.fn(),
}))

vi.mock('../../api/coachApi', () => ({
  fetchCoachDetails: vi.fn(),
  updateTeamAssignments: vi.fn(),
}))

const coach: CoachResponse = {
  id: 'coach-1',
  first_name: 'Asha',
  last_name: 'Patel',
  email: 'asha@vkca.test',
  role: 'assistant coach',
  is_active: true,
  version_number: 3,
  created_at: '',
  updated_at: '',
  teams: [{ id: 'team-1', name: 'U11 Falcons' }],
}

const teamsPage = {
  teams: [
    {
      id: 'team-1',
      name: 'U11 Falcons',
      age_group: 'U11' as const,
      player_count: 8,
      created_at: '',
      updated_at: '',
      version_number: 1,
    },
    {
      id: 'team-2',
      name: 'U13 Lions',
      age_group: 'U13' as const,
      player_count: 11,
      created_at: '',
      updated_at: '',
      version_number: 2,
    },
  ],
  page: 1,
  page_size: 100,
  total_teams: 2,
  total_pages: 1,
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  document.body.style.overflow = ''
})

describe('TeamAssignmentsModal', () => {
  it('shows all teams and submits the complete changed assignment set', async () => {
    const onSaved = vi.fn()
    vi.mocked(fetchTeams).mockResolvedValue(teamsPage)
    vi.mocked(updateTeamAssignments).mockResolvedValue({
      ...coach,
      version_number: 4,
      teams: [{ id: 'team-2', name: 'U13 Lions' }],
    })

    render(
      <TeamAssignmentsModal
        coach={coach}
        currentUserRole="head coach"
        onClose={vi.fn()}
        onSaved={onSaved}
      />,
    )

    const current = await screen.findByRole('checkbox', { name: /U11 Falcons/i })
    const next = screen.getByRole('checkbox', { name: /U13 Lions/i })
    expect(current).toBeChecked()
    expect(next).not.toBeChecked()

    fireEvent.click(current)
    fireEvent.click(next)
    fireEvent.click(screen.getByRole('button', { name: 'Save assignments' }))

    await waitFor(() =>
      expect(updateTeamAssignments).toHaveBeenCalledWith(coach.id, {
        team_ids: ['team-2'],
        version_number: 3,
      }),
    )
    expect(onSaved).toHaveBeenCalledWith({
      ...coach,
      version_number: 4,
      teams: [{ id: 'team-2', name: 'U13 Lions' }],
    })
  })

  it('confirms before discarding unsaved selection changes', async () => {
    const onClose = vi.fn()
    vi.mocked(fetchTeams).mockResolvedValue(teamsPage)
    render(
      <TeamAssignmentsModal
        coach={coach}
        currentUserRole="head coach"
        onClose={onClose}
        onSaved={vi.fn()}
      />,
    )

    fireEvent.click(
      await screen.findByRole('checkbox', { name: /U13 Lions/i }),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(
      screen.getByRole('alertdialog', { name: 'You have unsaved changes' }),
    ).toBeVisible()
    expect(onClose).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Continue editing' }))
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    fireEvent.click(screen.getByRole('button', { name: 'Discard changes' }))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('shows safe loading, empty, validation, permission, and conflict states', async () => {
    vi.mocked(fetchTeams).mockResolvedValue({ ...teamsPage, teams: [] })
    const { rerender } = render(
      <TeamAssignmentsModal
        coach={{ ...coach, teams: [] }}
        currentUserRole="head coach"
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    )
    expect(screen.getByRole('status')).toHaveTextContent('Loading teams')
    expect(
      await screen.findByText('No teams are available to assign yet.'),
    ).toBeVisible()

    cleanup()
    vi.mocked(fetchTeams).mockResolvedValue(teamsPage)
    vi.mocked(updateTeamAssignments)
      .mockRejectedValueOnce(
        new ApiClientError(400, { detail: 'team_ids: invalid team' }),
      )
      .mockRejectedValueOnce(
        new ApiClientError(403, { detail: 'backend detail' }),
      )
      .mockRejectedValueOnce(
        new ApiClientError(409, { detail: 'Stale version' }),
      )
    render(
      <TeamAssignmentsModal
        coach={coach}
        currentUserRole="head coach"
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    )
    fireEvent.click(
      await screen.findByRole('checkbox', { name: /U13 Lions/i }),
    )
    const save = screen.getByRole('button', { name: 'Save assignments' })
    fireEvent.click(save)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Check the selected teams and try again.',
    )
    fireEvent.click(save)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'You do not have permission to edit team assignments.',
    )
    fireEvent.click(save)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This coach was updated by another user.',
    )
    expect(rerender).toBeTypeOf('function')
  })

  it('reloads current assignments after a version conflict before another save', async () => {
    const onCoachReloaded = vi.fn()
    vi.mocked(fetchTeams).mockResolvedValue(teamsPage)
    vi.mocked(updateTeamAssignments)
      .mockRejectedValueOnce(
        new ApiClientError(409, { detail: 'Stale version' }),
      )
      .mockResolvedValueOnce({
        ...coach,
        version_number: 5,
        teams: [{ id: 'team-2', name: 'U13 Lions' }],
      })
    vi.mocked(fetchCoachDetails).mockResolvedValue({
      ...coach,
      version_number: 4,
      teams: [{ id: 'team-2', name: 'U13 Lions' }],
    })

    render(
      <TeamAssignmentsModal
        coach={coach}
        currentUserRole="head coach"
        onClose={vi.fn()}
        onCoachReloaded={onCoachReloaded}
        onSaved={vi.fn()}
      />,
    )

    fireEvent.click(
      await screen.findByRole('checkbox', { name: /U13 Lions/i }),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Save assignments' }))
    expect(
      await screen.findByText(/updated by another user/i),
    ).toBeVisible()
    expect(screen.getByRole('button', { name: 'Save assignments' })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: 'Reload' }))
    await waitFor(() =>
      expect(fetchCoachDetails).toHaveBeenCalledWith(coach.id),
    )
    expect(onCoachReloaded).toHaveBeenCalledWith({
      ...coach,
      version_number: 4,
      teams: [{ id: 'team-2', name: 'U13 Lions' }],
    })
    expect(
      screen.getByRole('checkbox', { name: /U13 Lions/i }),
    ).toBeChecked()
  })

  it('does not render for Assistant Coaches or inactive coaches', () => {
    const { rerender } = render(
      <TeamAssignmentsModal
        coach={coach}
        currentUserRole="assistant coach"
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    rerender(
      <TeamAssignmentsModal
        coach={{ ...coach, is_active: false }}
        currentUserRole="head coach"
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
