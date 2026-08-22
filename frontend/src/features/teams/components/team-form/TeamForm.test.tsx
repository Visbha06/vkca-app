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
  fetchTeamRoster,
  fetchTeams,
  updateTeam,
} from '@features/teams/api/teamApi'
import TeamForm from '@features/teams/components/team-form/TeamForm'
import TeamFormModal from '@features/teams/components/team-form/TeamFormModal'
import type {
  TeamResponse,
  TeamRosterResponse,
  TeamRosterSelection,
  TeamUpdatePayload,
} from '@features/teams/types/team'

vi.mock('@features/teams/api/teamApi', () => ({
  createTeam: vi.fn(),
  fetchTeamRoster: vi.fn(),
  fetchTeams: vi.fn(),
  updateTeam: vi.fn(),
}))

const team: TeamResponse = {
  id: 'team-1',
  name: 'Falcons',
  age_group: 'U13',
  player_count: 7,
  created_at: '',
  updated_at: '',
  version_number: 3,
}

function rosterPlayers(): TeamRosterSelection[] {
  return Array.from({ length: 7 }, (_, index) => ({
    player_id: `player-${index + 1}`,
    first_name: `Player${index + 1}`,
    last_name: 'VKCA',
    is_active: true,
  }))
}

function rosterResponse(
  players = rosterPlayers(),
): TeamRosterResponse {
  return {
    team_id: team.id,
    players: players.map((player, index) => ({
      ...player,
      roster_order: index + 1,
    })),
  }
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  document.body.style.overflow = ''
})

describe('TeamForm', () => {
  it('renders 15 empty create slots and reports missing required values', () => {
    const onSubmit = vi.fn()
    render(
      <TeamForm
        onCancel={vi.fn()}
        onSubmit={onSubmit}
      />,
    )

    expect(screen.getAllByRole('combobox', { name: /Player \d+/ }))
      .toHaveLength(15)
    fireEvent.click(screen.getByRole('button', { name: 'Create team' }))

    expect(screen.getByText('Enter a team name.')).toBeVisible()
    expect(screen.getByText('Choose an age group.')).toBeVisible()
    expect(screen.getByText('Select at least 7 players.')).toBeVisible()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('rejects duplicate players at the form boundary', () => {
    const duplicate = rosterPlayers()[0]
    const onSubmit = vi.fn()
    render(
      <TeamForm
        initialRoster={[
          duplicate,
          duplicate,
          ...rosterPlayers().slice(2),
        ]}
        onCancel={vi.fn()}
        onSubmit={onSubmit}
      />,
    )

    fireEvent.change(screen.getByLabelText('Team name'), {
      target: { value: 'Falcons' },
    })
    fireEvent.change(screen.getByLabelText('Age group'), {
      target: { value: 'U13' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create team' }))

    expect(screen.getByText('Each player can only be selected once.'))
      .toBeVisible()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits a normalized create payload with seven ordered players', () => {
    const onSubmit = vi.fn()
    render(
      <TeamForm
        initialRoster={rosterPlayers()}
        onCancel={vi.fn()}
        onSubmit={onSubmit}
      />,
    )

    fireEvent.change(screen.getByLabelText('Team name'), {
      target: { value: '  Falcons  ' },
    })
    fireEvent.change(screen.getByLabelText('Age group'), {
      target: { value: 'U13' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create team' }))

    expect(onSubmit).toHaveBeenCalledWith({
      name: 'Falcons',
      age_group: 'U13',
      player_ids: rosterPlayers().map((player) => player.player_id),
    })
  })

  it('submits the roster order set with keyboard move controls', () => {
    const onSubmit = vi.fn()
    render(
      <TeamForm
        initialRoster={rosterPlayers()}
        onCancel={vi.fn()}
        onSubmit={onSubmit}
      />,
    )

    fireEvent.change(screen.getByLabelText('Team name'), {
      target: { value: 'Falcons' },
    })
    fireEvent.change(screen.getByLabelText('Age group'), {
      target: { value: 'U13' },
    })
    fireEvent.click(
      screen.getByRole('button', { name: 'Move Player2 VKCA up' }),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Create team' }))

    expect(onSubmit).toHaveBeenCalledWith({
      name: 'Falcons',
      age_group: 'U13',
      player_ids: [
        'player-2',
        'player-1',
        'player-3',
        'player-4',
        'player-5',
        'player-6',
        'player-7',
      ],
    })
  })

  it('prefills edit values and includes the current version in the payload', () => {
    const onSubmit = vi.fn()
    render(
      <TeamForm
        team={team}
        roster={rosterResponse()}
        onCancel={vi.fn()}
        onSubmit={onSubmit}
      />,
    )

    expect(screen.getByLabelText('Team name')).toHaveValue('Falcons')
    expect(screen.getByLabelText('Age group')).toHaveValue('U13')
    expect(screen.getByDisplayValue('Player1 VKCA')).toBeVisible()
    expect(screen.getByDisplayValue('3')).toHaveAttribute(
      'name',
      'version_number',
    )
    fireEvent.change(screen.getByLabelText('Team name'), {
      target: { value: 'Eagles' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    const payload = onSubmit.mock.calls[0][0] as TeamUpdatePayload
    expect(payload).toEqual({
      name: 'Eagles',
      age_group: 'U13',
      player_ids: rosterPlayers().map((player) => player.player_id),
      version_number: 3,
    })
  })
})

describe('TeamFormModal edit safeguards', () => {
  it('offers a one-click reload after a stale-version conflict', async () => {
    const latestTeam = {
      ...team,
      name: 'Latest Falcons',
      version_number: 4,
    }
    vi.mocked(updateTeam).mockRejectedValue(
      new ApiClientError(409, { detail: 'Stale version.' }),
    )
    vi.mocked(fetchTeams).mockResolvedValue({
      teams: [latestTeam],
      page: 1,
      page_size: 100,
      total_teams: 1,
      total_pages: 1,
    })
    vi.mocked(fetchTeamRoster).mockResolvedValue(rosterResponse())
    render(
      <TeamFormModal
        team={team}
        roster={rosterResponse()}
        onClose={vi.fn()}
        onSaved={vi.fn()}
        onPlayerInfo={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This team was updated by another coach.',
    )
    fireEvent.click(
      screen.getByRole('button', { name: 'Reload latest team' }),
    )

    await waitFor(() =>
      expect(screen.getByLabelText('Team name'))
        .toHaveValue('Latest Falcons'),
    )
    expect(fetchTeams).toHaveBeenCalledWith({ page: 1, pageSize: 100 })
    expect(fetchTeamRoster).toHaveBeenCalledWith(team.id)
  })

  it('keeps dirty edits until the coach explicitly discards them', () => {
    const onClose = vi.fn()
    render(
      <TeamFormModal
        team={team}
        roster={rosterResponse()}
        onClose={onClose}
        onSaved={vi.fn()}
        onPlayerInfo={vi.fn()}
      />,
    )

    fireEvent.change(screen.getByLabelText('Team name'), {
      target: { value: 'Changed locally' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Close edit team' }))
    expect(
      screen.getByRole('alertdialog', { name: 'You have unsaved changes' }),
    ).toBeVisible()

    fireEvent.click(screen.getByRole('button', { name: 'Continue editing' }))
    expect(screen.getByLabelText('Team name')).toHaveValue('Changed locally')
    fireEvent.click(screen.getByRole('button', { name: 'Close edit team' }))
    fireEvent.click(screen.getByRole('button', { name: 'Discard changes' }))
    expect(onClose).toHaveBeenCalledOnce()
  })
})
