// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import type { AuthUser } from '../auth/types'
import PlayersPage from '../pages/PlayersPage'
import type { PaginatedPlayerResponse, PlayerResponse } from '../types/player'
import {
  createPlayer,
  fetchPlayer,
  fetchPlayers,
  fetchTeamsForFilter,
  updatePlayer,
} from '../api/playerApi'

vi.mock('../api/playerApi', () => ({
  createPlayer: vi.fn(),
  fetchPlayer: vi.fn(),
  fetchPlayers: vi.fn(),
  fetchTeamsForFilter: vi.fn(),
  updatePlayer: vi.fn(),
}))

const player: PlayerResponse = {
  id: 'player-1',
  first_name: 'Asha',
  last_name: 'Singh',
  date_of_birth: '2008-04-24',
  bio: null,
  batting_style: 'right',
  bowling_style: 'right-arm medium',
  player_type: 'all-rounder',
  player_metadata: {},
  is_active: true,
  created_at: '2026-07-01T10:00:00Z',
  updated_at: '2026-07-15T10:00:00Z',
  version_number: 1,
  teams: [{ id: 'team-1', name: 'Junior XI' }],
}

const firstPage: PaginatedPlayerResponse = {
  players: [player],
  page: 1,
  page_size: 20,
  total_players: 21,
  total_pages: 2,
  has_previous: false,
  has_next: true,
}

const headCoach: AuthUser = {
  id: 'user-1',
  first_name: 'Vikram',
  last_name: 'Kumar',
  email: 'coach@vkca.test',
  role: 'head coach',
  is_active: true,
  created_at: '2026-07-01T09:00:00Z',
  updated_at: '2026-07-19T09:00:00Z',
  session: {
    session_id: 'session-1',
    created_at: '2026-07-19T09:00:00Z',
    last_used_at: '2026-07-19T09:00:00Z',
    expires_at: '2026-08-18T09:00:00Z',
  },
}

function authValue(user: AuthUser): AuthContextValue {
  return {
    user,
    accessToken: 'test-token',
    isAuthenticated: true,
    isInitializing: false,
    isLoginPending: false,
    isLogoutPending: false,
    login: vi.fn(),
    logout: vi.fn(),
    refreshSession: vi.fn(),
    updateUser: vi.fn(),
  }
}

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>
}

function renderPage(user = headCoach, initialEntry = '/players') {
  return render(
    <AuthContext.Provider value={authValue(user)}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <PlayersPage />
        <LocationProbe />
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

beforeEach(() => {
  vi.mocked(fetchTeamsForFilter).mockResolvedValue([
    { id: 'team-1', name: 'Junior XI' },
  ])
  vi.mocked(fetchPlayers).mockResolvedValue(firstPage)
  vi.mocked(createPlayer).mockResolvedValue({
    ...player,
    id: 'player-2',
    first_name: 'Maya',
    last_name: 'Patel',
  })
  vi.mocked(fetchPlayer).mockResolvedValue(player)
  vi.mocked(updatePlayer).mockResolvedValue({
    ...player,
    first_name: 'Asha-Rae',
    version_number: 2,
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('PlayersPage', () => {
  it('fetches and renders players, teams, pagination, and coach controls', async () => {
    renderPage()

    expect(screen.getByRole('status')).toHaveTextContent('Loading players')
    expect(await screen.findByText('Asha Singh')).toBeVisible()
    expect(fetchPlayers).toHaveBeenCalledWith(
      { page: 1, pageSize: 20 },
      expect.any(AbortSignal),
    )
    expect(screen.getByRole('option', { name: 'Junior XI' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Add Player' })).toBeVisible()
    expect(screen.getByRole('navigation', { name: 'Player pages' })).toBeVisible()
  })

  it('filters by team, resets to page 1, and sends unassigned correctly', async () => {
    renderPage()
    await screen.findByText('Asha Singh')

    const filter = screen.getByRole('combobox', { name: 'Filter by team' })
    fireEvent.change(filter, { target: { value: 'team-1' } })
    await waitFor(() =>
      expect(fetchPlayers).toHaveBeenLastCalledWith(
        { page: 1, pageSize: 20, teamId: 'team-1' },
        expect.any(AbortSignal),
      ),
    )

    fireEvent.change(filter, { target: { value: '__unassigned__' } })
    await waitFor(() =>
      expect(fetchPlayers).toHaveBeenLastCalledWith(
        { page: 1, pageSize: 20, unassigned: true },
        expect.any(AbortSignal),
      ),
    )
  })

  it('pages, opens details, closes with Escape, and restores card focus', async () => {
    renderPage()
    const card = await screen.findByRole('button', { name: /view asha singh/i })
    card.focus()
    fireEvent.click(card)
    expect(screen.getByRole('dialog', { name: 'Asha Singh' })).toBeVisible()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(card).toHaveFocus()

    fireEvent.click(screen.getByRole('button', { name: 'Next page' }))
    await waitFor(() =>
      expect(fetchPlayers).toHaveBeenLastCalledWith(
        { page: 2, pageSize: 20 },
        expect.any(AbortSignal),
      ),
    )
  })

  it('shows empty and safe error states with retry', async () => {
    vi.mocked(fetchPlayers).mockResolvedValueOnce({
      ...firstPage,
      players: [],
      total_players: 0,
      total_pages: 0,
      has_next: false,
    })
    const { unmount } = renderPage()
    expect(await screen.findByText('No active players are available.')).toBeVisible()
    unmount()

    vi.mocked(fetchPlayers)
      .mockRejectedValueOnce(new Error('raw backend details'))
      .mockResolvedValueOnce(firstPage)
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to load players. Please try again.',
    )
    expect(screen.queryByText(/raw backend/i)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('Asha Singh')).toBeVisible()
  })

  it('hides Add and Edit Player controls from player-role users', async () => {
    renderPage({ ...headCoach, role: 'player' })
    fireEvent.click(
      await screen.findByRole('button', { name: /view asha singh/i }),
    )
    expect(screen.queryByRole('button', { name: 'Add Player' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Edit Player' })).not.toBeInTheDocument()
  })

  it('creates a player from the coach action and refreshes the list', async () => {
    renderPage()
    await screen.findByText('Asha Singh')
    fireEvent.click(screen.getByRole('button', { name: 'Add Player' }))

    fireEvent.change(screen.getByRole('textbox', { name: 'First name' }), {
      target: { value: 'Maya' },
    })
    fireEvent.change(screen.getByRole('textbox', { name: 'Last name' }), {
      target: { value: 'Patel' },
    })
    fireEvent.change(screen.getByLabelText('Date of birth'), {
      target: { value: '2009-06-12' },
    })
    fireEvent.change(screen.getByRole('combobox', { name: 'Batting style' }), {
      target: { value: 'left' },
    })
    fireEvent.change(screen.getByRole('combobox', { name: 'Bowling style' }), {
      target: { value: 'left-arm orthodox' },
    })
    fireEvent.change(screen.getByRole('combobox', { name: 'Player type' }), {
      target: { value: 'all-rounder' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create player' }))

    await waitFor(() => expect(createPlayer).toHaveBeenCalledTimes(1))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Maya Patel was added successfully.',
    )
    await waitFor(() => expect(fetchPlayers).toHaveBeenCalledTimes(2))
  })

  it('opens the Add Player modal from the dashboard action query and clears it', async () => {
    renderPage(headCoach, '/players?action=add')

    expect(await screen.findByRole('dialog', { name: 'Add player' })).toBeVisible()
    await waitFor(() =>
      expect(screen.getByTestId('location')).toHaveTextContent('/players'),
    )
    expect(screen.getByTestId('location')).not.toHaveTextContent('action=add')
  })

  it('closes details, edits the player, refreshes the list, and reopens fresh details', async () => {
    renderPage()
    fireEvent.click(
      await screen.findByRole('button', { name: /view asha singh/i }),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Edit Player' }))

    expect(
      screen.queryByRole('dialog', { name: 'Asha Singh' }),
    ).not.toBeInTheDocument()
    expect(
      screen.getByRole('dialog', { name: 'Edit Asha Singh' }),
    ).toBeVisible()

    fireEvent.change(screen.getByRole('textbox', { name: 'First name' }), {
      target: { value: 'Asha-Rae' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    await waitFor(() =>
      expect(updatePlayer).toHaveBeenCalledWith(
        'player-1',
        expect.objectContaining({
          first_name: 'Asha-Rae',
          version_number: 1,
        }),
      ),
    )
    expect(
      await screen.findByRole('dialog', { name: 'Asha-Rae Singh' }),
    ).toBeVisible()
    expect(screen.getByRole('status')).toHaveTextContent(
      'Asha-Rae Singh was updated successfully.',
    )
    await waitFor(() => expect(fetchPlayers).toHaveBeenCalledTimes(2))
  })
})
