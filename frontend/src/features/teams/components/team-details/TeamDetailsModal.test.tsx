// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import TeamDetailsModal from '@features/teams/components/team-details/TeamDetailsModal'
import { fetchTeamRoster } from '@features/teams/api/teamApi'
import type { TeamResponse } from '@features/teams/types/team'

vi.mock('@features/teams/api/teamApi', () => ({
  fetchTeamRoster: vi.fn(),
}))

const team: TeamResponse = { id: 'team-1', name: 'Falcons', age_group: 'U13', player_count: 1, created_at: '', updated_at: '', version_number: 1 }

afterEach(() => { cleanup(); vi.clearAllMocks(); document.body.style.overflow = '' })

describe('TeamDetailsModal', () => {
  it('renders team information and its ordered roster', async () => {
    vi.mocked(fetchTeamRoster).mockResolvedValue({ team_id: 'team-1', players: [{ player_id: 'p1', first_name: 'Asha', last_name: 'Singh', is_active: false, roster_order: 1 }] })
    render(<TeamDetailsModal team={team} canManageTeams={false} onClose={vi.fn()} onPlayerInfo={vi.fn()} />)
    expect(screen.getByRole('dialog', { name: 'Falcons' })).toBeVisible()
    expect(await screen.findByText('Asha Singh')).toBeVisible()
    expect(screen.getByText('Inactive')).toBeVisible()
  })

  it('shows an empty roster and closes with its close button', async () => {
    vi.mocked(fetchTeamRoster).mockResolvedValue({ team_id: 'team-1', players: [] })
    const onClose = vi.fn()
    render(<TeamDetailsModal team={team} canManageTeams={false} onClose={onClose} onPlayerInfo={vi.fn()} />)
    expect(await screen.findByText('No players are currently assigned to this team.')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Close team details' }))
    expect(onClose).toHaveBeenCalledOnce()
  })
})
