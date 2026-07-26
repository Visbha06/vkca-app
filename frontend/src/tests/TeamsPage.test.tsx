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

vi.mock('../api/teamApi', () => ({ fetchTeams: vi.fn(), fetchTeamRoster: vi.fn() }))
vi.mock('../api/playerApi', () => ({ fetchPlayer: vi.fn() }))

const team: TeamResponse = { id: 'team-1', name: 'Falcons', age_group: 'U13', player_count: 8, created_at: '2026-07-25T10:00:00Z', updated_at: '2026-07-25T10:00:00Z', version_number: 1 }
const coach: AuthUser = { id: 'u1', first_name: 'Vikram', last_name: 'Kumar', email: 'coach@vkca.test', role: 'head coach', is_active: true, created_at: '', updated_at: '', session: { session_id: 's1', created_at: '', last_used_at: '', expires_at: '' } }
const player: PlayerResponse = { id: 'player-1', first_name: 'Asha', last_name: 'Singh', date_of_birth: '2008-04-24', bio: null, batting_style: 'right', bowling_style: 'right-arm medium', player_type: 'batter', player_metadata: {}, is_active: true, created_at: '', updated_at: '', version_number: 1, teams: [] }

function authValue(): AuthContextValue {
  return { user: coach, accessToken: 'token', isAuthenticated: true, isInitializing: false, isLoginPending: false, isLogoutPending: false, login: vi.fn(), logout: vi.fn(), refreshSession: vi.fn(), updateUser: vi.fn() }
}

function renderPage() {
  return render(<AuthContext.Provider value={authValue()}><TeamsPage /></AuthContext.Provider>)
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('TeamsPage', () => {
  it('shows loading then team cards, pagination, and role-gated create action', async () => {
    vi.mocked(fetchTeams).mockResolvedValue({ teams: [team], page: 1, page_size: 12, total_teams: 13, total_pages: 2 })
    renderPage()
    expect(screen.getByRole('status')).toHaveTextContent('Loading teams')
    expect(await screen.findByRole('button', { name: 'View Falcons' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Create Team' })).toBeDisabled()
    expect(screen.getByRole('navigation', { name: 'Player pages' })).toBeVisible()
  })

  it('shows an empty state, safe error message, and retries', async () => {
    vi.mocked(fetchTeams).mockResolvedValueOnce({ teams: [], page: 1, page_size: 12, total_teams: 0, total_pages: 0 })
    renderPage()
    expect(await screen.findByText('No teams are available.')).toBeVisible()
    cleanup()
    vi.mocked(fetchTeams).mockRejectedValueOnce(new Error('internal details')).mockResolvedValueOnce({ teams: [team], page: 1, page_size: 12, total_teams: 1, total_pages: 1 })
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load teams. Please try again.')
    expect(screen.queryByText(/internal details/i)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(fetchTeams).toHaveBeenCalledTimes(3))
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
})
