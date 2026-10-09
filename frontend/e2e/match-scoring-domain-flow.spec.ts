import { expect, test, type Page, type Route } from '@playwright/test'

type Variant = 'internal' | 'external'

interface CapturedRequest {
  method: string
  path: string
  authorization: string | undefined
  body: Record<string, unknown> | null
}

interface MockScoringState {
  variant: Variant
  matchId: string
  inningsId: string
  matchVersion: number
  inningsVersion: number
  deliveryId: string
  revisionNumber: number
  totalRuns: number
  lifecycle: 'in_progress' | 'abandoned'
  resultCode: 'pending' | 'no_result'
  policy: Record<string, unknown>
  sides: Array<Record<string, unknown>>
  participants: Array<Record<string, unknown>>
}

const apiOrigin = 'http://localhost:8000'
const accessToken = 'playwright-scoring-head-coach-token'

function entityId(variant: Variant, suffix: number): string {
  const offset = variant === 'internal' ? 1000 : 2000
  return `00000000-0000-4000-8000-${String(offset + suffix).padStart(12, '0')}`
}

function makeState(variant: Variant): MockScoringState {
  const matchId = entityId(variant, 101)
  const homeSideId = entityId(variant, 1)
  const awaySideId = entityId(variant, 2)
  const homeTeamId = entityId(variant, 11)
  const awayTeamId = entityId(variant, 12)
  const sides = [
    {
      id: homeSideId,
      side_code: 'home',
      side_kind: 'academy',
      team_id: homeTeamId,
      display_name_snapshot: 'Academy Home',
    },
    {
      id: awaySideId,
      side_code: 'away',
      side_kind: variant === 'external' ? 'external' : 'academy',
      team_id: variant === 'external' ? null : awayTeamId,
      display_name_snapshot: variant === 'external' ? 'Visitors XI' : 'Academy Away',
    },
  ]
  const participants = [
    ...[1, 2, 3].map((position) => ({
      id: entityId(variant, position),
      side_id: homeSideId,
      participant_kind: 'internal',
      player_id: entityId(variant, position + 20),
      display_name_snapshot: `Home Player ${position}`,
      batting_order_position: position,
    })),
    ...[1, 2, 3].map((position) => ({
      id: entityId(variant, position + 10),
      side_id: awaySideId,
      participant_kind: variant === 'external' ? 'external' : 'internal',
      player_id:
        variant === 'external'
          ? null
          : entityId(variant, position + 30),
      display_name_snapshot:
        variant === 'external' ? `Opponent Player ${position}` : `Away Player ${position}`,
      batting_order_position: position,
    })),
  ]
  return {
    variant,
    matchId,
    inningsId: entityId(variant, 77),
    matchVersion: 1,
    inningsVersion: 0,
    deliveryId: entityId(variant, 99),
    revisionNumber: 1,
    totalRuns: 0,
    lifecycle: 'in_progress',
    resultCode: 'pending',
    policy: {
      id: entityId(variant, 88),
      policy_code: 'T20',
      policy_version: 1,
      capability_profile: 'T20',
      capability_version: 1,
      innings_sequence: ['home', 'away'],
      innings_per_side: 1,
      legal_ball_limit: 120,
      over_length_legal_balls: 6,
      bowler_quota_legal_balls: 24,
      wicket_limit: 10,
      consecutive_overs_prohibited: true,
      target_mode: 'prior_innings_plus_one',
      allowed_dismissal_types: ['bowled', 'caught'],
      allowed_transition_types: ['retired_hurt', 'retired_hurt_return'],
      allowed_innings_completion_modes: ['all_out', 'legal_ball_limit', 'target_reached'],
      allowed_match_completion_modes: ['abandonment'],
      allowed_result_codes: ['pending', 'win_by_runs', 'win_by_wickets', 'tie', 'no_result'],
      allow_declaration: false,
      allow_draw: false,
      allow_manual_completion: false,
      explicit_match_completion_boundary: 'none',
      version_number: 1,
    },
    sides,
    participants,
  }
}

function blocking(kind: 'none' | 'match_completed' | 'match_abandoned') {
  return {
    kind,
    is_blocked: kind !== 'none',
    reason_code: kind === 'none' ? null : kind,
  }
}

async function respond(
  route: Route,
  status: number,
  value: Record<string, unknown>,
) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    headers: { 'access-control-allow-origin': '*' },
    body: JSON.stringify(value),
  })
}

async function handleScoringRoute(
  route: Route,
  active: () => MockScoringState,
  captured: CapturedRequest[],
) {
  const request = route.request()
  if (request.method() === 'OPTIONS') {
    await route.fulfill({
      status: 204,
      headers: {
        'access-control-allow-origin': '*',
        'access-control-allow-headers': 'authorization,content-type',
        'access-control-allow-methods': 'GET,POST,PUT,OPTIONS',
      },
    })
    return
  }

  const url = new URL(request.url())
  const path = url.pathname.replace('/api/v1', '')
  const state = active()
  const requestBody = request.postData()
    ? (request.postDataJSON() as Record<string, unknown>)
    : null
  captured.push({
    method: request.method(),
    path,
    authorization: request.headers().authorization,
    body: requestBody,
  })
  if (request.headers().authorization !== `Bearer ${accessToken}`) {
    await respond(route, 401, { detail: 'Not authenticated' })
    return
  }

  if (request.method() === 'POST' && path === '/matches') {
    await respond(route, 201, {
      id: state.matchId,
      match_date: '2026-09-22',
      format: 'T20',
      venue: 'Playwright Ground',
      result: 'Scheduled',
      version_number: 1,
      participants:
        state.variant === 'external'
          ? {
              kind: 'external',
              academy_team: { id: state.sides[0].team_id, name: 'Academy Home' },
              opponent_name: 'Visitors XI',
              academy_side: 'home',
            }
          : {
              kind: 'internal',
              home_team: { id: state.sides[0].team_id, name: 'Academy Home' },
              away_team: { id: state.sides[1].team_id, name: 'Academy Away' },
            },
    })
    return
  }

  if (request.method() === 'PUT' && path === `/matches/${state.matchId}/configuration`) {
    state.matchVersion = 2
    await respond(route, 200, {
      match_id: state.matchId,
      match_version_number: state.matchVersion,
      lifecycle_state: 'scheduled',
      scoring_authority: 'delivery_history',
      configured_at: '2026-09-22T12:00:00Z',
      policy: state.policy,
      sides: state.sides,
      participants: state.participants,
      blocking_state: blocking('none'),
    })
    return
  }

  if (request.method() === 'POST' && path === `/matches/${state.matchId}/innings`) {
    state.matchVersion += 1
    state.inningsVersion = 1
    await respond(route, 200, {
      id: state.inningsId,
      match_id: state.matchId,
      match_version_number: state.matchVersion,
      innings_number: 1,
      lifecycle_state: 'in_progress',
      version_number: state.inningsVersion,
      legal_balls: 0,
      total_runs: 0,
      wickets_lost: 0,
      striker_participant_id: state.participants[0].id,
      non_striker_participant_id: state.participants[1].id,
      current_bowler_participant_id: state.participants[3].id,
      blocking_state: blocking('none'),
    })
    return
  }

  if (
    request.method() === 'POST' &&
    new RegExp(`^/matches/${state.matchId}/innings/[^/]+/deliveries$`).test(path)
  ) {
    if (requestBody?.innings_version_number !== state.inningsVersion) {
      await respond(route, 409, {
        detail: 'The innings version is stale.',
        code: 'scoring_version_conflict',
      })
      return
    }
    state.inningsVersion += 1
    state.totalRuns += Number(requestBody.runs_off_bat ?? 0)
    await respond(route, 200, {
      id: state.deliveryId,
      innings_id: state.inningsId,
      attempted_sequence: requestBody.attempted_sequence,
      active_revision: {
        id: entityId(state.variant, 110),
        revision_number: state.revisionNumber,
        revision_state: 'active',
        striker_participant_id: requestBody.striker_participant_id,
        non_striker_participant_id: requestBody.non_striker_participant_id,
        bowler_participant_id: requestBody.bowler_participant_id,
        runs_off_bat: requestBody.runs_off_bat,
        extras: {
          wide_runs: 0,
          no_ball_penalty_runs: 0,
          bye_runs: 0,
          leg_bye_runs: 0,
          penalty_runs: 0,
        },
        total_runs: requestBody.runs_off_bat,
        is_legal: true,
        completed_runs: requestBody.runs_off_bat,
        balls_faced: true,
        bowler_conceded_runs: requestBody.runs_off_bat,
        over_number: 0,
        ball_in_over: 1,
        wicket: null,
        replacement_reason: null,
        supersedes_revision_id: null,
        recorded_by_user_id: '00000000-0000-4000-8000-000000000099',
        recorded_at: '2026-09-22T12:05:00Z',
      },
      innings_version_number: state.inningsVersion,
      innings_total_runs: state.totalRuns,
      innings_legal_balls: 1,
      innings_wickets_lost: 0,
      striker_participant_id: requestBody.striker_participant_id,
      non_striker_participant_id: requestBody.non_striker_participant_id,
      current_bowler_participant_id: requestBody.bowler_participant_id,
      blocking_state: blocking('none'),
    })
    return
  }

  const correctionPath = new RegExp(
    `^/matches/${state.matchId}/innings/[^/]+/deliveries/[^/]+/correction$`,
  )
  if (request.method() === 'POST' && correctionPath.test(path)) {
    if (
      requestBody?.match_version_number !== state.matchVersion ||
      requestBody?.innings_version_number !== state.inningsVersion
    ) {
      await respond(route, 409, {
        detail: 'The scoring version is stale.',
        code: 'scoring_version_conflict',
      })
      return
    }
    const replacement = requestBody.replacement as Record<string, unknown>
    state.totalRuns = Number(replacement.runs_off_bat)
    state.revisionNumber += 1
    state.matchVersion += 1
    state.inningsVersion += 1
    await respond(route, 200, {
      id: state.deliveryId,
      innings_id: state.inningsId,
      match_id: state.matchId,
      match_version_number: state.matchVersion,
      match_lifecycle_state: 'in_progress',
      innings_lifecycle_state: 'in_progress',
      innings_version_number: state.inningsVersion,
      active_revision: {
        id: entityId(state.variant, 111),
        revision_number: state.revisionNumber,
        revision_state: 'active',
        runs_off_bat: replacement.runs_off_bat,
        total_runs: replacement.runs_off_bat,
        supersedes_revision_id: entityId(state.variant, 110),
        replacement_reason: requestBody.reason,
      },
      innings_total_runs: state.totalRuns,
      result_code: state.resultCode,
      result_details: {},
      blocking_state: blocking('none'),
      match_blocking_state: blocking('none'),
    })
    return
  }

  if (request.method() === 'POST' && path === `/matches/${state.matchId}/completion`) {
    if (requestBody?.match_version_number !== state.matchVersion) {
      await respond(route, 409, {
        detail: 'The Match version is stale.',
        code: 'scoring_version_conflict',
      })
      return
    }
    state.lifecycle = 'abandoned'
    state.resultCode = 'no_result'
    state.matchVersion += 1
    await respond(route, 200, {
      match_id: state.matchId,
      match_version_number: state.matchVersion,
      lifecycle_state: state.lifecycle,
      result_code: state.resultCode,
      result_details: { reason: requestBody.reason },
      blocking_state: blocking('match_abandoned'),
    })
    return
  }

  if (request.method() === 'GET' && path === `/matches/${state.matchId}/scorecard`) {
    await respond(route, 200, {
      match_id: state.matchId,
      match_version_number: state.matchVersion,
      lifecycle_state: state.lifecycle,
      scoring_authority: 'delivery_history',
      result_code: state.resultCode,
      result_details: {},
      policy: state.policy,
      sides: state.sides,
      participants: state.participants,
      innings: [
        {
          id: state.inningsId,
          innings_number: 1,
          lifecycle_state: 'in_progress',
          total_runs: state.totalRuns,
          legal_balls: 1,
          wickets_lost: 0,
          version_number: state.inningsVersion,
          blocking_state: blocking(
            state.lifecycle === 'abandoned' ? 'match_abandoned' : 'none',
          ),
        },
      ],
      participant_performances: [],
      blocking_state: blocking(
        state.lifecycle === 'abandoned' ? 'match_abandoned' : 'none',
      ),
      projection_revision: state.inningsVersion,
    })
    return
  }

  await respond(route, 404, { detail: `Unhandled mock request: ${request.method()} ${path}` })
}

async function apiRequest(
  page: Page,
  method: string,
  path: string,
  body: Record<string, unknown> | null = null,
) {
  return page.evaluate(
    async ({ apiOriginValue, token, methodValue, pathValue, bodyValue }) => {
      const response = await fetch(`${apiOriginValue}/api/v1${pathValue}`, {
        method: methodValue,
        headers: {
          Authorization: `Bearer ${token}`,
          ...(bodyValue === null ? {} : { 'Content-Type': 'application/json' }),
        },
        ...(bodyValue === null ? {} : { body: JSON.stringify(bodyValue) }),
      })
      return {
        status: response.status,
        body: (await response.json()) as Record<string, unknown>,
      }
    },
    {
      apiOriginValue: apiOrigin,
      token: accessToken,
      methodValue: method,
      pathValue: path,
      bodyValue: body,
    },
  )
}

test('authenticated request-level Match scoring flow covers internal and external identity', async ({
  page,
}) => {
  const captured: CapturedRequest[] = []
  let active = makeState('internal')
  await page.route('http://localhost:8000/api/v1/**', (route) =>
    handleScoringRoute(route, () => active, captured),
  )
  await page.goto('about:blank')

  for (const variant of ['internal', 'external'] as const) {
    active = makeState(variant)
    const external = variant === 'external'
    const createBody = external
      ? {
          match_date: '2026-09-22',
          format: 'T20',
          venue: 'Playwright Ground',
          result: 'Scheduled',
          participants: {
            participant_type: 'external',
            academy_team_id: active.sides[0].team_id,
            external_opponent_name: 'Visitors XI',
            academy_side: 'home',
          },
        }
      : {
          match_date: '2026-09-22',
          format: 'T20',
          venue: 'Playwright Ground',
          result: 'Scheduled',
          participants: {
            participant_type: 'internal',
            home_team_id: active.sides[0].team_id,
            away_team_id: active.sides[1].team_id,
          },
        }
    const initialized = await apiRequest(page, 'POST', '/matches', createBody)
    expect(initialized.status).toBe(201)
    expect(initialized.body.id).toBe(active.matchId)

    const configBody = {
      match_version_number: 1,
      format: 'T20',
      policy: {
        policy_code: 'T20',
        capability_profile: 'T20',
        innings_sequence: ['home', 'away'],
      },
      sides: active.sides.map((side) => ({
        side_code: side.side_code,
        side_kind: side.side_kind,
        team_id: side.team_id,
        display_name: side.display_name_snapshot,
      })),
      participants: active.participants.map((participant) => ({
        side_code: participant.side_id === active.sides[0].id ? 'home' : 'away',
        participant_kind: participant.participant_kind,
        ...(participant.player_id === null
          ? { display_name: participant.display_name_snapshot }
          : { player_id: participant.player_id }),
        batting_order_position: participant.batting_order_position,
      })),
    }
    const configured = await apiRequest(
      page,
      'PUT',
      `/matches/${active.matchId}/configuration`,
      configBody,
    )
    expect(configured.status).toBe(200)
    expect((configured.body.policy as Record<string, unknown>).policy_code).toBe('T20')
    const configuredParticipants = configured.body.participants as Array<
      Record<string, unknown>
    >
    if (external) {
      const opposition = configuredParticipants.filter(
        (participant) => participant.participant_kind === 'external',
      )
      expect(opposition).toHaveLength(3)
      expect(opposition.every((participant) => participant.player_id === null)).toBe(true)
      expect(opposition.every((participant) => !('user_id' in participant))).toBe(true)
    }

    const started = await apiRequest(
      page,
      'POST',
      `/matches/${active.matchId}/innings`,
      {
        match_version_number: active.matchVersion,
        innings_number: 1,
        opening_striker_participant_id: active.participants[0].id,
        opening_non_striker_participant_id: active.participants[1].id,
        opening_bowler_participant_id: active.participants[3].id,
      },
    )
    expect(started.status).toBe(200)

    const inningsId = active.inningsId
    const deliveryPath = `/matches/${active.matchId}/innings/${inningsId}/deliveries`
    const deliveryBody = {
      innings_version_number: active.inningsVersion,
      attempted_sequence: 1,
      striker_participant_id: active.participants[0].id,
      non_striker_participant_id: active.participants[1].id,
      bowler_participant_id: active.participants[3].id,
      runs_off_bat: 4,
      extras: {},
    }
    const scored = await apiRequest(page, 'POST', deliveryPath, deliveryBody)
    expect(scored.status).toBe(200)
    expect((scored.body.active_revision as Record<string, unknown>).total_runs).toBe(4)

    const conflict = await apiRequest(page, 'POST', deliveryPath, deliveryBody)
    expect(conflict.status).toBe(409)
    expect(conflict.body.code).toBe('scoring_version_conflict')

    const readBeforeCorrection = await apiRequest(
      page,
      'GET',
      `/matches/${active.matchId}/scorecard`,
    )
    expect(readBeforeCorrection.status).toBe(200)
    expect(readBeforeCorrection.body.scoring_authority).toBe('delivery_history')

    const corrected = await apiRequest(
      page,
      'POST',
      `${deliveryPath}/${active.deliveryId}/correction`,
      {
        match_version_number: active.matchVersion,
        innings_version_number: active.inningsVersion,
        expected_revision_number: 1,
        reason: 'Correct the observed boundary',
        replacement: {
          striker_participant_id: active.participants[0].id,
          non_striker_participant_id: active.participants[1].id,
          bowler_participant_id: active.participants[3].id,
          runs_off_bat: 6,
          extras: {},
        },
      },
    )
    expect(corrected.status).toBe(200)
    expect(
      (corrected.body.active_revision as Record<string, unknown>).revision_number,
    ).toBe(2)

    const completed = await apiRequest(
      page,
      'POST',
      `/matches/${active.matchId}/completion`,
      {
        match_version_number: active.matchVersion,
        completion_kind: 'abandonment',
        reason: 'Weather stopped play',
      },
    )
    expect(completed.status).toBe(200)
    expect(completed.body.lifecycle_state).toBe('abandoned')
    expect(completed.body.result_code).toBe('no_result')

    const readAfterCompletion = await apiRequest(
      page,
      'GET',
      `/matches/${active.matchId}/scorecard`,
    )
    expect(readAfterCompletion.status).toBe(200)
    expect(readAfterCompletion.body.blocking_state).toMatchObject({
      kind: 'match_abandoned',
      is_blocked: true,
    })
  }

  expect(captured.length).toBeGreaterThan(0)
  expect(captured.every((request) => request.authorization === `Bearer ${accessToken}`)).toBe(
    true,
  )
  expect(captured.some((request) => request.path.endsWith('/configuration'))).toBe(true)
  expect(captured.some((request) => request.path.endsWith('/correction'))).toBe(true)
  expect(captured.some((request) => request.path.endsWith('/completion'))).toBe(true)
  const externalConfig = captured.find(
    (request) =>
      request.path.endsWith('/configuration') &&
      request.body?.format === 'T20' &&
      (request.body.participants as Array<Record<string, unknown>>).some(
        (participant) => participant.participant_kind === 'external',
      ),
  )
  expect(externalConfig).toBeDefined()
  expect(JSON.stringify(externalConfig?.body)).not.toContain('user_id')
  expect(JSON.stringify(externalConfig?.body)).not.toContain('account_id')
})
