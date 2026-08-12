import type { Page } from '@playwright/test'
import type { AuthApiState } from './auth-api-mock'
import type { DashboardResponse } from '@features/dashboard/types/dashboard'
import type { DashboardActivityEvent } from '@features/dashboard/types/dashboard'
import type {
  PlayerAccountAssociationResponse,
  PlayerAccountSnapshot,
} from '@features/players/types/player'

export type DashboardFixtureRole =
  | 'head coach'
  | 'assistant coach'
  | 'player'
  | 'unlinked player'

const teamId = '33333333-3333-4333-8333-333333333333'
const playerId = 'player-asha'
const account: PlayerAccountSnapshot = {
  id: '77777777-7777-4777-8777-777777777777',
  display_name: 'Rohan Account',
  email: 'rohan.player@example.com',
  role: 'player',
  is_active: true,
}

const events = Array.from({ length: 5 }, (_, index) => ({
  occurrence_id: `dashboard-event-${index + 1}`,
  event_date: `2026-08-${String(12 + index).padStart(2, '0')}`,
  start_time: '17:00:00',
  end_time: '18:30:00',
  name: index === 0 ? 'Batting fundamentals' : `Academy practice ${index + 1}`,
  event_type: 'practice' as const,
  age_groups: ['U15' as const],
}))

const recentActivity = Array.from({ length: 4 }, (_, index) => ({
  id: `44444444-4444-4444-8444-44444444444${index}`,
  actor_display_name: 'Asha Coach',
  action_type: 'player.created' as const,
  action_category: 'player' as const,
  target_label: `Academy Player ${index + 1}`,
  summary: `Asha Coach added Academy Player ${index + 1}`,
  created_at: `2026-08-1${index}T18:00:00Z`,
}))

function readyDashboard(
  role: Exclude<DashboardFixtureRole, 'unlinked player'>,
): DashboardResponse {
  const isPlayer = role === 'player'
  return {
    user: {
      id: isPlayer
        ? '55555555-5555-4555-8555-555555555555'
        : '11111111-1111-4111-8111-111111111111',
      display_name: isPlayer ? 'Priya Player' : 'Asha Coach',
      role,
    },
    dashboard_state: 'ready',
    summary: {
      training: { status: 'ready', data: events[0] },
      next_match: {
        status: 'ready',
        data: {
          id: '22222222-2222-4222-8222-222222222222',
          match_date: '2026-08-15',
          format: 'T20',
          participants: {
            kind: 'external',
            academy_team: { id: teamId, name: 'U15 Falcons' },
            opponent_name: 'Northside CC',
            academy_side: 'home',
          },
        },
      },
      player_slot: isPlayer
        ? {
            status: 'ready',
            data: {
              kind: 'player_teams',
              team_count: 1,
              team_names: ['U15 Falcons'],
            },
          }
        : {
            status: 'ready',
            data: {
              kind: 'active_player_count',
              count: 42,
              team_count: role === 'head coach' ? 4 : 1,
            },
          },
    },
    upcoming_events: { status: 'ready', data: events },
    context:
      role === 'head coach'
        ? {
            status: 'ready',
            data: {
              kind: 'recent_activity',
              events: recentActivity,
              view_all_path: '/audit-log',
            },
          }
        : {
            status: 'ready',
            data: {
              kind: 'my_teams',
              teams: [
                {
                  id: teamId,
                  name: 'U15 Falcons',
                  age_group: 'U15',
                  active_player_count: 12,
                  coaches: isPlayer
                    ? [
                        {
                          id: '66666666-6666-4666-8666-666666666666',
                          display_name: 'Asha Coach',
                        },
                      ]
                    : [],
                  next_event: events[0],
                },
              ],
              view_all_path: '/teams',
            },
          },
  }
}

function unlinkedDashboard(): DashboardResponse {
  const message = 'Contact your Head Coach to link your Player profile.'
  return {
    user: {
      id: '88888888-8888-4888-8888-888888888888',
      display_name: 'Unlinked Player',
      role: 'player',
    },
    dashboard_state: 'unlinked',
    summary: {
      training: { status: 'unlinked', message },
      next_match: { status: 'unlinked', message },
      player_slot: { status: 'unlinked', message },
    },
    upcoming_events: { status: 'unlinked', message },
    context: { status: 'unlinked', message },
  }
}

export interface RoleAwareDashboardApiState {
  accountAssociation: PlayerAccountAssociationResponse
  accountMutationRequests: number
  dashboardDelayMs: number
  dashboardRequests: number
  emptyEvents: boolean
  failNextDashboard: boolean
  matchManagementRequests: number
  role: DashboardFixtureRole
  setRole: (role: DashboardFixtureRole) => void
}

interface RoleAwareDashboardFixtureOptions {
  recentActivity?: () => DashboardActivityEvent[]
}

function dashboardFor(
  state: RoleAwareDashboardApiState,
  options: RoleAwareDashboardFixtureOptions,
): DashboardResponse {
  if (state.role === 'unlinked player') return unlinkedDashboard()
  const dashboard = readyDashboard(state.role)
  if (
    state.role === 'head coach'
    && options.recentActivity !== undefined
  ) {
    dashboard.context = {
      status: 'ready',
      data: {
        kind: 'recent_activity',
        events: options.recentActivity().slice(0, 4),
        view_all_path: '/audit-log',
      },
    }
  }
  if (!state.emptyEvents) return dashboard
  return {
    ...dashboard,
    upcoming_events: {
      status: 'empty',
      message: 'No upcoming events in your scope.',
    },
  }
}

export async function installRoleAwareDashboardApiMock(
  page: Page,
  auth: AuthApiState,
  options: RoleAwareDashboardFixtureOptions = {},
): Promise<RoleAwareDashboardApiState> {
  const state: RoleAwareDashboardApiState = {
    accountAssociation: {
      player_id: playerId,
      account: null,
      player_version_number: 1,
    },
    accountMutationRequests: 0,
    dashboardDelayMs: 0,
    dashboardRequests: 0,
    emptyEvents: false,
    failNextDashboard: false,
    matchManagementRequests: 0,
    role: 'head coach',
    setRole(role) {
      state.role = role
      auth.user.role = role === 'unlinked player' ? 'player' : role
      auth.user.first_name = role.includes('player') ? 'Priya' : 'Asha'
      auth.user.last_name = role.includes('player') ? 'Player' : 'Coach'
    },
  }

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const { pathname } = new URL(request.url())

    if (pathname === '/api/v1/dashboard' && request.method() === 'GET') {
      state.dashboardRequests += 1
      if (state.dashboardDelayMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, state.dashboardDelayMs))
      }
      if (state.failNextDashboard) {
        await route.fulfill({
          status: 500,
          json: { detail: 'Dashboard fixture failure' },
        })
        return
      }
      await route.fulfill({ status: 200, json: dashboardFor(state, options) })
      return
    }

    if (
      pathname === '/api/v1/players/account-linking/users'
      && request.method() === 'GET'
    ) {
      await route.fulfill({
        status: 200,
        json: {
          users: [account],
          page: 1,
          page_size: 20,
          total_users: 1,
          total_pages: 1,
        },
      })
      return
    }

    const accountPath = pathname.match(
      /^\/api\/v1\/players\/([^/]+)\/account(?:\/(reassign))?$/,
    )
    if (accountPath) {
      if (request.method() === 'GET') {
        await route.fulfill({ status: 200, json: state.accountAssociation })
        return
      }
      state.accountMutationRequests += 1
      if (request.method() === 'PUT') {
        state.accountAssociation = {
          player_id: accountPath[1] ?? playerId,
          account,
          player_version_number:
            state.accountAssociation.player_version_number + 1,
        }
      } else if (request.method() === 'DELETE') {
        state.accountAssociation = {
          player_id: accountPath[1] ?? playerId,
          account: null,
          player_version_number:
            state.accountAssociation.player_version_number + 1,
        }
      } else if (request.method() === 'POST' && accountPath[2] === 'reassign') {
        state.accountAssociation = {
          player_id: accountPath[1] ?? playerId,
          account,
          player_version_number:
            state.accountAssociation.player_version_number + 1,
        }
      } else {
        await route.fallback()
        return
      }
      await route.fulfill({ status: 200, json: state.accountAssociation })
      return
    }

    if (pathname.startsWith('/api/v1/matches')) {
      state.matchManagementRequests += 1
    }
    await route.fallback()
  })

  return state
}
