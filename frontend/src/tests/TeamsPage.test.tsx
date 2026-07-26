// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import TeamsPage from '../pages/TeamsPage'
import { fetchPlayer } from '../api/playerApi'
import { fetchTeamRoster, fetchTeams } from '../api/teamApi'
import type { AuthUser } from '../auth/types'
import type { PlayerResponse } from '../types/player'
import type { TeamResponse } from '../types/team'

vi.mock('../api/teamApi', () => ({
  createTeam: vi.fn(),
  fetchTeams: vi.fn(),
  fetchTeamRoster: vi.fn(),
  updateTeam: vi.fn(),
}))
vi.mock('../api/playerApi', () => ({ fetchPlayer: vi.fn() }))

const team: TeamResponse = { id: 'team-1', name: 'Falcons', age_group: 'U13', player_count: 8, created_at: '2026-07-25T10:00:00Z', updated_at: '2026-07-25T10:00:00Z', version_number: 1 }
const coach: AuthUser = { id: 'u1', first_name: 'Vikram', last_name: 'Kumar', email: 'coach@vkca.test', role: 'head coach', is_active: true, created_at: '', updated_at: '', session: { session_id: 's1', created_at: '', last_used_at: '', expires_at: '' } }
const player: PlayerResponse = { id: 'player-1', first_name: 'Asha', last_name: 'Singh', date_of_birth: '2008-04-24', bio: null, batting_style: 'right', bowling_style: 'right-arm medium', player_type: 'batter', player_metadata: {}, is_active: true, created_at: '', updated_at: '', version_number: 1, teams: [] }

function authValue(): AuthContextValue {
  return { user: coach, accessToken: 'token', isAuthenticated: true, isInitializing: false, isLoginPending: false, isLogoutPending: false, login: vi.fn(), logout: vi.fn(), refreshSession: vi.fn(), updateUser: vi.fn() }
}

function renderPage(value = authValue()) {
  return render(<AuthContext.Provider value={value}><TeamsPage /></AuthContext.Provider>)
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('TeamsPage', () => {
  it('shows loading then team rows, count status, pagination, and role-gated create action', async () => {
    vi.mocked(fetchTeams).mockResolvedValue({ teams: [team], page: 1, page_size: 12, total_teams: 13, total_pages: 2 })
    renderPage()
    expect(screen.getByRole('status')).toHaveTextContent('Loading teams')
    expect(await screen.findByRole('button', { name: 'View Falcons' })).toBeVisible()
    expect(screen.getByText('13 active teams')).toBeVisible()
    expect(screen.getByRole('list', { name: 'Teams' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Create Team' })).toBeEnabled()
    fireEvent.click(screen.getByRole('button', { name: 'Create Team' }))
    expect(screen.getByRole('dialog', { name: 'Create Team' })).toBeVisible()
    expect(screen.getByRole('navigation', { name: 'Team pages' })).toBeVisible()
  })

  it('offers coaches a create action in the true empty state', async () => {
    vi.mocked(fetchTeams).mockResolvedValueOnce({ teams: [], page: 1, page_size: 12, total_teams: 0, total_pages: 0 })
    renderPage()
    expect(await screen.findByText('Create the first academy team')).toBeVisible()
    expect(screen.getAllByRole('button', { name: 'Create Team' })).toHaveLength(2)
  })

  it('does not offer an unavailable action to read-only users', async () => {
    vi.mocked(fetchTeams).mockResolvedValueOnce({ teams: [], page: 1, page_size: 12, total_teams: 0, total_pages: 0 })
    renderPage({ ...authValue(), user: { ...coach, role: 'player' } })
    expect(await screen.findByText('No academy teams are available yet')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Create Team' })).not.toBeInTheDocument()
  })

  it('shows a safe error message and retries', async () => {
    cleanup()
    vi.mocked(fetchTeams).mockRejectedValueOnce(new Error('internal details')).mockResolvedValueOnce({ teams: [team], page: 1, page_size: 12, total_teams: 1, total_pages: 1 })
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load teams. Please try again.')
    expect(screen.queryByText(/internal details/i)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(fetchTeams).toHaveBeenCalledTimes(2))
  })

  it('filters teams by name and age group and clears a filtered empty state', async () => {
    const seniorTeam = {
      ...team,
      id: 'team-2',
      name: 'Senior Strikers',
      age_group: 'U15' as const,
    }
    vi.mocked(fetchTeams).mockResolvedValue({
      teams: [team, seniorTeam],
      page: 1,
      page_size: 12,
      total_teams: 2,
      total_pages: 1,
    })
    renderPage()

    await screen.findByRole('button', { name: 'View Falcons' })
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search teams' }), {
      target: { value: 'senior' },
    })
    expect(screen.queryByRole('button', { name: 'View Falcons' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'View Senior Strikers' })).toBeVisible()
    expect(screen.getByText('1 team found')).toBeVisible()

    fireEvent.change(screen.getByRole('combobox', { name: 'Filter by age group' }), {
      target: { value: 'U13' },
    })
    expect(screen.getByText('No teams match these filters')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(screen.getByRole('button', { name: 'View Falcons' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'View Senior Strikers' })).toBeVisible()
  })

  it('replaces team details with player details when roster info is opened', async () => {
    vi.mocked(fetchTeams).mockResolvedValue({ teams: [team], page: 1, page_size: 12, total_teams: 1, total_pages: 1 })
    vi.mocked(fetchTeamRoster).mockResolvedValue({ team_id: 'team-1', players: [{ player_id: 'player-1', first_name: 'Asha', last_name: 'Singh', is_active: true, roster_order: 1 }] })
    vi.mocked(fetchPlayer).mockResolvedValue(player)
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'View Falcons' }))
    expect(await screen.findByRole('dialog', { name: 'Falcons' })).toBeVisible()
    fireEvent.click(await screen.findByRole('button', { name: 'View Asha Singh' }))

    expect(screen.queryByRole('dialog', { name: 'Falcons' })).not.toBeInTheDocument()
    expect(await screen.findByRole('dialog', { name: 'Asha Singh' })).toBeVisible()
  })

  it('replaces team details with a prefilled edit form', async () => {
    vi.mocked(fetchTeams).mockResolvedValue({ teams: [team], page: 1, page_size: 12, total_teams: 1, total_pages: 1 })
    vi.mocked(fetchTeamRoster).mockResolvedValue({ team_id: 'team-1', players: Array.from({ length: 7 }, (_, index) => ({ player_id: `player-${index + 1}`, first_name: `Player${index + 1}`, last_name: 'VKCA', is_active: true, roster_order: index + 1 })) })
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'View Falcons' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Team' }))

    expect(screen.queryByRole('dialog', { name: 'Falcons' })).not.toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: 'Edit Falcons' })).toBeVisible()
    expect(screen.getByLabelText('Team name')).toHaveValue('Falcons')
  })
})
