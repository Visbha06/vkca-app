import { expect, test, type Page } from '@playwright/test'
import { installAuthApiMock } from './auth-api-mock'
import type {
  PaginatedPlayerResponse,
  PlayerResponse,
} from '../src/types/player'
import type {
  PaginatedTeamResponse,
  TeamCreatePayload,
  TeamResponse,
  TeamRosterResponse,
  TeamUpdatePayload,
} from '../src/types/team'

const timestamp = '2026-07-25T18:00:00Z'

function makePlayers(): PlayerResponse[] {
  return Array.from({ length: 10 }, (_, index) => ({
    id: `player-${index + 1}`,
    first_name: `Player${index + 1}`,
    last_name: 'VKCA',
    date_of_birth: `200${index}-01-01`,
    bio: null,
    batting_style: 'right',
    bowling_style: 'right-arm medium',
    player_type: 'all-rounder',
    player_metadata: {},
    is_active: true,
    created_at: timestamp,
    updated_at: timestamp,
    version_number: 1,
    teams: [],
  }))
}

interface TeamsApiState {
  createPayloads: TeamCreatePayload[]
  players: PlayerResponse[]
  rosterOrder: string[]
  teams: TeamResponse[]
  updatePayloads: TeamUpdatePayload[]
}

function paginatedPlayers(
  players: PlayerResponse[],
  page: number,
  pageSize: number,
): PaginatedPlayerResponse {
  const totalPlayers = players.length
  return {
    players: players.slice((page - 1) * pageSize, page * pageSize),
    page,
    page_size: pageSize,
    total_players: totalPlayers,
    total_pages: Math.ceil(totalPlayers / pageSize),
    has_previous: page > 1,
    has_next: page * pageSize < totalPlayers,
  }
}

function paginatedTeams(
  teams: TeamResponse[],
  page: number,
  pageSize: number,
): PaginatedTeamResponse {
  return {
    teams: teams.slice((page - 1) * pageSize, page * pageSize),
    page,
    page_size: pageSize,
    total_teams: teams.length,
    total_pages: Math.ceil(teams.length / pageSize),
  }
}

async function installTeamsApiMock(page: Page): Promise<TeamsApiState> {
  const state: TeamsApiState = {
    createPayloads: [],
    players: makePlayers(),
    rosterOrder: [],
    teams: [],
    updatePayloads: [],
  }

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const { pathname, searchParams } = url

    if (pathname === '/api/v1/players' && request.method() === 'GET') {
      const search = searchParams.get('search')?.trim().toLowerCase() ?? ''
      const pageNumber = Number(searchParams.get('page') ?? 1)
      const pageSize = Number(searchParams.get('page_size') ?? 20)
      const matchingPlayers = state.players.filter((player) =>
        `${player.first_name} ${player.last_name}`
          .toLowerCase()
          .includes(search),
      )
      await route.fulfill({
        status: 200,
        json: paginatedPlayers(matchingPlayers, pageNumber, pageSize),
      })
      return
    }

    if (pathname === '/api/v1/teams' && request.method() === 'GET') {
      const pageNumber = Number(searchParams.get('page') ?? 1)
      const pageSize = Number(searchParams.get('page_size') ?? 12)
      await route.fulfill({
        status: 200,
        json: paginatedTeams(state.teams, pageNumber, pageSize),
      })
      return
    }

    if (pathname === '/api/v1/teams' && request.method() === 'POST') {
      const payload = request.postDataJSON() as TeamCreatePayload
      state.createPayloads.push(payload)
      state.rosterOrder = [...payload.player_ids]
      const createdTeam: TeamResponse = {
        id: 'team-created',
        name: payload.name,
        age_group: payload.age_group,
        player_count: payload.player_ids.length,
        created_at: timestamp,
        updated_at: timestamp,
        version_number: 1,
      }
      state.teams = [createdTeam]
      await route.fulfill({ status: 201, json: createdTeam })
      return
    }

    const rosterMatch = pathname.match(
      /^\/api\/v1\/teams\/([^/]+)\/players$/,
    )
    if (rosterMatch && request.method() === 'GET') {
      const response: TeamRosterResponse = {
        team_id: rosterMatch[1],
        players: state.rosterOrder.map((playerId, index) => {
          const player = state.players.find(({ id }) => id === playerId)
          if (player === undefined) {
            throw new Error(`Unknown mocked player ${playerId}`)
          }
          return {
            player_id: player.id,
            first_name: player.first_name,
            last_name: player.last_name,
            is_active: player.is_active,
            roster_order: index + 1,
          }
        }),
      }
      await route.fulfill({ status: 200, json: response })
      return
    }

    const teamMatch = pathname.match(/^\/api\/v1\/teams\/([^/]+)$/)
    if (teamMatch && request.method() === 'PUT') {
      const payload = request.postDataJSON() as TeamUpdatePayload
      const currentTeam = state.teams.find(({ id }) => id === teamMatch[1])
      if (currentTeam === undefined) {
        await route.fulfill({
          status: 404,
          json: { detail: 'Team not found.' },
        })
        return
      }
      state.updatePayloads.push(payload)
      state.rosterOrder = [...payload.player_ids]
      const updatedTeam: TeamResponse = {
        ...currentTeam,
        name: payload.name,
        age_group: payload.age_group,
        player_count: payload.player_ids.length,
        updated_at: '2026-07-25T18:05:00Z',
        version_number: currentTeam.version_number + 1,
      }
      state.teams = [updatedTeam]
      await route.fulfill({ status: 200, json: updatedTeam })
      return
    }

    await route.fallback()
  })

  return state
}

function playerNames(state: TeamsApiState): string[] {
  return state.rosterOrder.map((playerId) => {
    const player = state.players.find(({ id }) => id === playerId)
    return `${player?.first_name} ${player?.last_name}`
  })
}

test.describe('teams interface', () => {
  test('logs in, creates and reorders a roster, edits it, and persists order after reload', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await installAuthApiMock(page, false)
    const api = await installTeamsApiMock(page)

    await page.goto('/teams')
    await expect(page).toHaveURL(/\/login\?redirect=%2Fteams$/)
    await page.getByLabel('Email address').fill('john.coach@vkca.test')
    await page.getByLabel('Password', { exact: true }).fill('CoachP@ssword1')
    await page.getByRole('button', { name: 'Log in' }).click()
    await expect(page).toHaveURL(/\/teams$/)
    await expect(page.getByRole('heading', { name: 'Teams' })).toBeVisible()

    await page.getByRole('button', { name: 'Create Team' }).click()
    await page.getByLabel('Team name').fill('Falcons E2E')
    await page.getByLabel('Age group').selectOption('U13')

    for (let index = 1; index <= 8; index += 1) {
      const input = page.getByRole('combobox', {
        name: `Player ${index} (${index <= 7 ? 'required' : 'optional'})`,
      })
      await input.fill(`Player${index}`)
      await page
        .getByRole('option', { name: `Player${index} VKCA`, exact: true })
        .click()
    }

    await page
      .getByRole('button', { name: 'Move Player8 VKCA up' })
      .click()
    await page
      .getByRole('button', { name: 'Move Player8 VKCA up' })
      .click()
    await page
      .getByRole('button', { name: 'Create team', exact: true })
      .click()

    await expect(
      page.getByText('Falcons E2E was created successfully.'),
    ).toBeVisible()
    expect(api.createPayloads).toHaveLength(1)
    expect(api.createPayloads[0].player_ids).toEqual([
      'player-1',
      'player-2',
      'player-3',
      'player-4',
      'player-5',
      'player-8',
      'player-6',
      'player-7',
    ])

    await page.getByRole('button', { name: 'View Falcons E2E' }).click()
    const createdDetails = page.getByRole('dialog', { name: 'Falcons E2E' })
    await expect(createdDetails).toBeVisible()
    await expect(createdDetails.locator('ol > li > div > p:first-child'))
      .toHaveText(playerNames(api))

    await createdDetails.getByRole('button', { name: 'Edit Team' }).click()
    await page
      .getByRole('button', { name: 'Move Player1 VKCA down' })
      .click()
    await page.getByLabel('Team name').fill('Falcons E2E Updated')
    await page.getByRole('button', { name: 'Save changes' }).click()

    await expect(
      page.getByText('Falcons E2E Updated was updated successfully.'),
    ).toBeVisible()
    expect(api.updatePayloads).toHaveLength(1)
    expect(api.rosterOrder).toEqual([
      'player-2',
      'player-1',
      'player-3',
      'player-4',
      'player-5',
      'player-8',
      'player-6',
      'player-7',
    ])

    await page.reload()
    await page
      .getByRole('button', { name: 'View Falcons E2E Updated' })
      .click()
    const reloadedDetails = page.getByRole('dialog', {
      name: 'Falcons E2E Updated',
    })
    await expect(reloadedDetails.locator('ol > li > div > p:first-child'))
      .toHaveText(playerNames(api))
  })
})
