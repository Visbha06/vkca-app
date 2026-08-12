import type { DashboardResponse } from '../types/dashboard'

export function dashboardFixture(
  overrides: Partial<DashboardResponse> = {},
): DashboardResponse {
  return {
    user: {
      id: '11111111-1111-4111-8111-111111111111',
      display_name: 'Asha Coach',
      role: 'head coach',
    },
    dashboard_state: 'ready',
    summary: {
      training: {
        status: 'ready',
        data: {
          occurrence_id: 'practice-1',
          event_date: '2026-08-12',
          start_time: '17:00:00',
          end_time: '18:30:00',
          name: 'Batting fundamentals',
          event_type: 'practice',
          age_groups: ['U15'],
        },
      },
      next_match: {
        status: 'ready',
        data: {
          id: '22222222-2222-4222-8222-222222222222',
          match_date: '2026-08-15',
          format: 'T20',
          participants: {
            kind: 'external',
            academy_team: {
              id: '33333333-3333-4333-8333-333333333333',
              name: 'U15 Falcons',
            },
            opponent_name: 'Northside CC',
            academy_side: 'home',
          },
        },
      },
      player_slot: {
        status: 'ready',
        data: {
          kind: 'active_player_count',
          count: 42,
          team_count: 4,
        },
      },
    },
    upcoming_events: {
      status: 'ready',
      data: [
        {
          occurrence_id: 'event-1',
          event_date: '2026-08-12',
          start_time: '17:00:00',
          end_time: '18:30:00',
          name: 'Batting fundamentals',
          event_type: 'practice',
          age_groups: ['U15'],
        },
      ],
    },
    context: {
      status: 'ready',
      data: {
        kind: 'recent_activity',
        events: [
          {
            id: '44444444-4444-4444-8444-444444444444',
            actor_display_name: 'Asha Coach',
            action_type: 'player.created',
            action_category: 'player',
            target_label: 'Rohan Player',
            summary: 'Asha Coach added Rohan Player',
            created_at: '2026-08-10T18:00:00Z',
          },
        ],
        view_all_path: '/audit-log',
      },
    },
    ...overrides,
  }
}

export function playerDashboardFixture({
  hasEvents = true,
  hasTeams = true,
  unlinked = false,
}: {
  hasEvents?: boolean
  hasTeams?: boolean
  unlinked?: boolean
} = {}): DashboardResponse {
  const contactMessage = 'Contact your Head Coach to link your Player profile.'
  if (unlinked) {
    return dashboardFixture({
      user: {
        id: '55555555-5555-4555-8555-555555555555',
        display_name: 'Priya Player',
        role: 'player',
      },
      dashboard_state: 'unlinked',
      summary: {
        training: { status: 'unlinked', message: contactMessage },
        next_match: { status: 'unlinked', message: contactMessage },
        player_slot: { status: 'unlinked', message: contactMessage },
      },
      upcoming_events: { status: 'unlinked', message: contactMessage },
      context: { status: 'unlinked', message: contactMessage },
    })
  }

  const base = dashboardFixture()
  return dashboardFixture({
    user: {
      id: '55555555-5555-4555-8555-555555555555',
      display_name: 'Priya Player',
      role: 'player',
    },
    summary: {
      ...base.summary,
      player_slot: hasTeams
        ? {
            status: 'ready',
            data: {
              kind: 'player_teams',
              team_count: 1,
              team_names: ['U15 Falcons'],
            },
          }
        : { status: 'empty', message: 'You are not on a team yet.' },
    },
    upcoming_events: hasEvents
      ? base.upcoming_events
      : { status: 'empty', message: 'No upcoming events in your scope.' },
    context: hasTeams
      ? {
          status: 'ready',
          data: {
            kind: 'my_teams',
            teams: [
              {
                id: '33333333-3333-4333-8333-333333333333',
                name: 'U15 Falcons',
                age_group: 'U15',
                active_player_count: 12,
                coaches: [],
                next_event: null,
              },
            ],
            view_all_path: '/teams',
          },
        }
      : { status: 'empty', message: 'You are not on a team yet.' },
  })
}
