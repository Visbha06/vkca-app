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
import { fetchPlayers } from '@features/players'
import TeamRosterList from '@features/teams/components/team-form/TeamRosterList'
import TeamRosterRow from '@features/teams/components/team-form/TeamRosterRow'
import type { PlayerResponse } from '@features/players'
import type { TeamRosterSelection } from '@features/teams/types/team'

vi.mock('@features/players', () => ({ fetchPlayers: vi.fn() }))

const player: PlayerResponse = {
  id: 'player-1',
  first_name: 'Asha',
  last_name: 'Singh',
  date_of_birth: '2008-04-24',
  bio: null,
  batting_style: 'right',
  bowling_style: 'right-arm medium',
  player_type: 'batter',
  player_metadata: {},
  is_active: true,
  created_at: '',
  updated_at: '',
  version_number: 1,
  teams: [],
}

const selection: TeamRosterSelection = {
  player_id: player.id,
  first_name: player.first_name,
  last_name: player.last_name,
  is_active: true,
}

function rosterSelections(count: number) {
  return Array.from({ length: count }, (_, index) => ({
    player_id: `player-${index + 1}`,
    first_name: `Player${index + 1}`,
    last_name: 'VKCA',
    is_active: true,
  }))
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('TeamRosterRow', () => {
  it('searches for active players and selects an available result', async () => {
    vi.mocked(fetchPlayers).mockResolvedValue({
      players: [player],
      page: 1,
      page_size: 50,
      total_players: 1,
      total_pages: 1,
      has_previous: false,
      has_next: false,
    })
    const onChange = vi.fn()
    render(
      <TeamRosterRow
        index={0}
        player={null}
        selectedPlayerIds={[]}
        onChange={onChange}
        onPlayerInfo={vi.fn()}
      />,
    )

    const search = screen.getByRole('combobox', {
      name: 'Player 1 (required)',
    })
    fireEvent.focus(search)
    fireEvent.change(search, { target: { value: 'Ash' } })

    expect(await screen.findByRole('option', { name: 'Asha Singh' }))
      .toBeVisible()
    expect(fetchPlayers).toHaveBeenCalledWith(
      { page: 1, pageSize: 50, search: 'Ash' },
      expect.any(AbortSignal),
    )
    fireEvent.click(screen.getByRole('option', { name: 'Asha Singh' }))
    expect(onChange).toHaveBeenCalledWith(selection)
  })

  it('disables empty-row actions and clears or inspects a selected player', () => {
    const onChange = vi.fn()
    const onPlayerInfo = vi.fn()
    const { rerender } = render(
      <TeamRosterRow
        index={7}
        player={null}
        selectedPlayerIds={[]}
        onChange={onChange}
        onPlayerInfo={onPlayerInfo}
      />,
    )

    expect(screen.getByRole('button', { name: 'View player 8 details' }))
      .toBeDisabled()
    expect(screen.getByRole('button', { name: 'Remove player 8' }))
      .toBeDisabled()

    rerender(
      <TeamRosterRow
        index={7}
        player={selection}
        selectedPlayerIds={[selection.player_id]}
        onChange={onChange}
        onPlayerInfo={onPlayerInfo}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'View Asha Singh' }))
    fireEvent.click(screen.getByRole('button', { name: 'Remove Asha Singh' }))

    expect(onPlayerInfo).toHaveBeenCalledWith(selection)
    expect(onChange).toHaveBeenCalledWith(null)
  })

  it('shows a recoverable error when player search fails', async () => {
    vi.mocked(fetchPlayers)
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({
        players: [player],
        page: 1,
        page_size: 50,
        total_players: 1,
        total_pages: 1,
        has_previous: false,
        has_next: false,
      })
    render(
      <TeamRosterRow
        index={0}
        player={null}
        selectedPlayerIds={[]}
        onChange={vi.fn()}
        onPlayerInfo={vi.fn()}
      />,
    )

    fireEvent.focus(
      screen.getByRole('combobox', { name: 'Player 1 (required)' }),
    )
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to search players.',
    )
    fireEvent.click(screen.getByRole('button', { name: 'Retry player search' }))

    await waitFor(() => expect(fetchPlayers).toHaveBeenCalledTimes(2))
    expect(await screen.findByRole('option', { name: 'Asha Singh' }))
      .toBeVisible()
  })

  it('excludes players already selected in another roster row', async () => {
    vi.mocked(fetchPlayers).mockResolvedValue({
      players: [player],
      page: 1,
      page_size: 50,
      total_players: 1,
      total_pages: 1,
      has_previous: false,
      has_next: false,
    })
    render(
      <TeamRosterRow
        index={1}
        player={null}
        selectedPlayerIds={[player.id]}
        onChange={vi.fn()}
        onPlayerInfo={vi.fn()}
      />,
    )

    fireEvent.focus(
      screen.getByRole('combobox', { name: 'Player 2 (required)' }),
    )

    expect(await screen.findByText('No players found')).toBeVisible()
    expect(screen.queryByRole('option', { name: 'Asha Singh' }))
      .not.toBeInTheDocument()
  })

  it('reorders the roster after dropping a player on a new position', () => {
    const onPlayersChange = vi.fn()
    const players = [
      ...rosterSelections(5),
      ...Array<TeamRosterSelection | null>(10).fill(null),
    ]
    render(
      <TeamRosterList
        players={players}
        disabled={false}
        onPlayersChange={onPlayersChange}
        onPlayerInfo={vi.fn()}
      />,
    )

    const draggedHandle = screen.getByLabelText('Drag Player5 VKCA to reorder')
    fireEvent.dragStart(draggedHandle)
    fireEvent.dragOver(screen.getByLabelText('Player 2 (required)'))
    fireEvent.drop(screen.getByLabelText('Player 2 (required)'))

    expect(onPlayersChange).toHaveBeenCalledWith([
      players[0],
      players[4],
      players[1],
      players[2],
      players[3],
      ...Array<TeamRosterSelection | null>(10).fill(null),
    ])
  })

  it('moves players with accessible controls and disables unavailable directions', () => {
    const onPlayersChange = vi.fn()
    const players = [
      ...rosterSelections(2),
      ...Array<TeamRosterSelection | null>(13).fill(null),
    ]
    render(
      <TeamRosterList
        players={players}
        disabled={false}
        onPlayersChange={onPlayersChange}
        onPlayerInfo={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: 'Move Player1 VKCA up' }))
      .toBeDisabled()
    expect(screen.getByRole('button', { name: 'Move Player2 VKCA down' }))
      .toBeDisabled()

    fireEvent.click(
      screen.getByRole('button', { name: 'Move Player2 VKCA up' }),
    )

    expect(onPlayersChange).toHaveBeenCalledWith([
      players[1],
      players[0],
      ...Array<TeamRosterSelection | null>(13).fill(null),
    ])
  })
})
