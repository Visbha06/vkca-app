import { expect, test, type Page } from '@playwright/test'
import type {
  CoachCreatePayload,
  CoachResponse,
  CoachTeamUpdatePayload,
  PaginatedCoachResponse,
} from '@features/coaches/types/coach'
import type {
  PaginatedTeamResponse,
  TeamResponse,
} from '@features/teams/types/team'
import { installAuthApiMock, mockAuthUser } from './auth-api-mock'

const timestamp = '2026-07-29T18:00:00Z'

interface CoachesApiState {
  coaches: CoachResponse[]
  createPayloads: CoachCreatePayload[]
  statusChanges: Array<'disable' | 'reactivate'>
  teamUpdatePayloads: CoachTeamUpdatePayload[]
  teams: TeamResponse[]
}

function paginateCoaches(
  coaches: CoachResponse[],
  page: number,
  pageSize: number,
): PaginatedCoachResponse {
  const totalCoaches = coaches.length
  const totalPages = Math.ceil(totalCoaches / pageSize)
  return {
    coaches: coaches.slice((page - 1) * pageSize, page * pageSize),
    page,
    page_size: pageSize,
    total_coaches: totalCoaches,
    total_pages: totalPages,
    has_previous: page > 1,
    has_next: page < totalPages,
  }
}

function paginatedTeams(teams: TeamResponse[]): PaginatedTeamResponse {
  return {
    teams,
    page: 1,
    page_size: 100,
    total_teams: teams.length,
    total_pages: teams.length === 0 ? 0 : 1,
  }
}

async function installCoachesApiMock(page: Page): Promise<CoachesApiState> {
  const state: CoachesApiState = {
    coaches: [
      {
        id: mockAuthUser.id,
        first_name: mockAuthUser.first_name,
        last_name: mockAuthUser.last_name,
        email: mockAuthUser.email,
        role: 'head coach',
        is_active: true,
        version_number: 1,
        created_at: timestamp,
        updated_at: timestamp,
        teams: [],
      },
    ],
    createPayloads: [],
    statusChanges: [],
    teamUpdatePayloads: [],
    teams: [
      {
        id: 'team-falcons',
        name: 'Falcons',
        age_group: 'U13',
        player_count: 9,
        created_at: timestamp,
        updated_at: timestamp,
        version_number: 1,
      },
      {
        id: 'team-strikers',
        name: 'Strikers',
        age_group: 'U15',
        player_count: 11,
        created_at: timestamp,
        updated_at: timestamp,
        version_number: 1,
      },
    ],
  }

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const { pathname, searchParams } = url

    if (pathname === '/api/v1/teams' && request.method() === 'GET') {
      await route.fulfill({ status: 200, json: paginatedTeams(state.teams) })
      return
    }

    if (pathname === '/api/v1/coaches' && request.method() === 'GET') {
      const status = searchParams.get('status') ?? 'active'
      const pageNumber = Number(searchParams.get('page') ?? 1)
      const pageSize = Number(searchParams.get('page_size') ?? 12)
      const matching = state.coaches.filter(
        (coach) =>
          status === 'all' ||
          (status === 'active' ? coach.is_active : !coach.is_active),
      )
      await route.fulfill({
        status: 200,
        json: paginateCoaches(matching, pageNumber, pageSize),
      })
      return
    }

    if (pathname === '/api/v1/coaches' && request.method() === 'POST') {
      const payload = request.postDataJSON() as CoachCreatePayload
      state.createPayloads.push(payload)
      const created: CoachResponse = {
        id: 'coach-created',
        first_name: payload.first_name,
        last_name: payload.last_name,
        email: payload.email,
        role: 'assistant coach',
        is_active: true,
        version_number: 1,
        created_at: timestamp,
        updated_at: timestamp,
        teams: state.teams
          .filter((team) => payload.team_ids?.includes(team.id))
          .map(({ id, name }) => ({ id, name })),
      }
      state.coaches.push(created)
      await route.fulfill({
        status: 201,
        json: {
          ...created,
          temporary_password: 'Aa1!coach-e2e-password',
        },
      })
      return
    }

    const coachMatch = pathname.match(/^\/api\/v1\/coaches\/([^/]+)$/)
    if (coachMatch && request.method() === 'GET') {
      const coach = state.coaches.find(({ id }) => id === coachMatch[1])
      await route.fulfill(
        coach === undefined
          ? { status: 404, json: { detail: 'Coach not found' } }
          : { status: 200, json: coach },
      )
      return
    }

    const assignmentMatch = pathname.match(
      /^\/api\/v1\/coaches\/([^/]+)\/teams$/,
    )
    if (assignmentMatch && request.method() === 'PUT') {
      const payload = request.postDataJSON() as CoachTeamUpdatePayload
      const coach = state.coaches.find(({ id }) => id === assignmentMatch[1])
      if (coach === undefined) {
        await route.fulfill({
          status: 404,
          json: { detail: 'Coach not found' },
        })
        return
      }
      state.teamUpdatePayloads.push(payload)
      coach.teams = state.teams
        .filter((team) => payload.team_ids.includes(team.id))
        .map(({ id, name }) => ({ id, name }))
      coach.version_number += 1
      coach.updated_at = '2026-07-29T18:05:00Z'
      await route.fulfill({ status: 200, json: coach })
      return
    }

    const statusMatch = pathname.match(
      /^\/api\/v1\/users\/([^/]+)\/(disable|reactivate)$/,
    )
    if (statusMatch && request.method() === 'POST') {
      const coach = state.coaches.find(({ id }) => id === statusMatch[1])
      if (coach === undefined) {
        await route.fulfill({ status: 404, json: { detail: 'User not found' } })
        return
      }
      const action = statusMatch[2] as 'disable' | 'reactivate'
      state.statusChanges.push(action)
      coach.is_active = action === 'reactivate'
      coach.version_number += 1
      coach.updated_at = '2026-07-29T18:04:00Z'
      await route.fulfill({
        status: 200,
        json: {
          id: coach.id,
          first_name: coach.first_name,
          last_name: coach.last_name,
          email: coach.email,
          role: coach.role,
          is_active: coach.is_active,
          version_number: coach.version_number,
          created_at: coach.created_at,
          updated_at: coach.updated_at,
        },
      })
      return
    }

    await route.fallback()
  })

  return state
}

test.describe('coaches portal', () => {
  test('completes the full Head Coach account and assignment journey', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await installAuthApiMock(page, false)
    const api = await installCoachesApiMock(page)

    await page.goto('/coaches')
    await expect(page).toHaveURL(/\/login\?redirect=%2Fcoaches$/)
    await page.getByLabel('Email address').fill('john.coach@vkca.test')
    await page.getByLabel('Password', { exact: true }).fill('CoachP@ssword1')
    await page.getByRole('button', { name: 'Log in' }).click()
    await expect(page).toHaveURL(/\/coaches$/)
    await expect(
      page.getByRole('heading', { name: 'Coaches Portal' }),
    ).toBeVisible()

    await page.getByRole('button', { name: 'Add Coach' }).click()
    await expect(
      page.getByRole('dialog', { name: 'Add Assistant Coach' }),
    ).toBeVisible()
    await page.getByRole('textbox', { name: 'First name' }).fill('Asha')
    await page.getByRole('textbox', { name: 'Last name' }).fill('Kapoor')
    await page
      .getByRole('textbox', { name: 'Email address' })
      .fill('asha.kapoor@vkca.test')
    await page.getByRole('checkbox', { name: /Falcons/ }).check()
    await page.getByRole('button', { name: 'Create coach' }).click()

    await expect(
      page.getByRole('heading', { name: 'Assistant Coach created' }),
    ).toBeVisible()
    await expect(page.getByLabel('Temporary password')).toHaveValue(
      'Aa1!coach-e2e-password',
    )
    expect(api.createPayloads).toEqual([
      {
        first_name: 'Asha',
        last_name: 'Kapoor',
        email: 'asha.kapoor@vkca.test',
        team_ids: ['team-falcons'],
      },
    ])
    await page.getByRole('button', { name: 'Done' }).click()
    await expect(
      page.getByRole('button', { name: 'View Asha Kapoor details' }),
    ).toBeVisible()

    await page
      .getByRole('combobox', { name: 'Coach status' })
      .selectOption('all')
    await page
      .getByRole('button', { name: 'View Asha Kapoor details' })
      .click()
    const details = page.getByRole('dialog', { name: 'Asha Kapoor' })
    await expect(details).toBeVisible()
    await expect(details.getByText('Falcons')).toBeVisible()

    await details.getByRole('button', { name: 'Deactivate coach' }).click()
    await expect(
      page.getByRole('alertdialog', { name: 'Deactivate Asha Kapoor?' }),
    ).toBeVisible()
    await page.getByRole('button', { name: 'Confirm deactivation' }).click()
    await expect(details.getByText('Inactive', { exact: true })).toBeVisible()
    await expect(
      page.getByRole('button', { name: 'View Asha Kapoor details' }),
    ).toHaveClass(/bg-slate-50/)
    expect(api.statusChanges).toEqual(['disable'])

    await details.getByRole('button', { name: 'Reactivate coach' }).click()
    await expect(details.getByText('Active', { exact: true })).toBeVisible()
    expect(api.statusChanges).toEqual(['disable', 'reactivate'])

    await details.getByRole('button', { name: 'Edit assignments' }).click()
    const assignments = page.getByRole('dialog', {
      name: 'Edit team assignments',
    })
    await expect(assignments).toBeVisible()
    await assignments.getByRole('checkbox', { name: /Falcons/ }).uncheck()
    await assignments.getByRole('checkbox', { name: /Strikers/ }).check()
    await assignments
      .getByRole('button', { name: 'Save assignments' })
      .click()

    await expect(assignments).toBeHidden()
    await expect(
      page.getByText('Team assignments for Asha Kapoor were updated.'),
    ).toBeVisible()
    await expect(
      page.getByRole('button', { name: 'View Asha Kapoor details' }),
    ).toContainText('Strikers')
    expect(api.teamUpdatePayloads).toEqual([
      {
        team_ids: ['team-strikers'],
        version_number: 3,
      },
    ])
  })
})
