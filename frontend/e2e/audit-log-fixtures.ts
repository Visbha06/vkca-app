import type { Page } from '@playwright/test'
import type {
  BusinessAuditEvent,
  BusinessAuditPageResponse,
} from '@features/audit/types/businessAudit'

export const BUSINESS_AUDIT_E2E_PATH = '/audit-log'

const actorId = '550e8400-e29b-41d4-a716-446655440000'

const initialEvents: BusinessAuditEvent[] = [
  {
    id: '00000000-0000-4000-8000-000000000102',
    actor_user_id: actorId,
    actor_display_name: 'John Coach',
    actor_role: 'head coach',
    action_type: 'calendar.standalone_created',
    action_category: 'calendar',
    target_entity_type: 'calendar_event',
    target_entity_id: '00000000-0000-4000-8000-000000000202',
    target_label: 'U15 batting practice',
    summary: 'John Coach scheduled U15 batting practice',
    metadata: { event_type: 'practice', scope: 'U15' },
    created_at: '2026-08-06T18:00:00Z',
    request_id: 'e2e-request-calendar',
  },
  {
    id: '00000000-0000-4000-8000-000000000101',
    actor_user_id: actorId,
    actor_display_name: 'John Coach',
    actor_role: 'head coach',
    action_type: 'team.created',
    action_category: 'team',
    target_entity_type: 'team',
    target_entity_id: '00000000-0000-4000-8000-000000000201',
    target_label: 'Junior XI',
    summary: 'John Coach created the Junior XI team',
    metadata: { age_group: 'U13', roster_count: 10 },
    created_at: '2026-08-06T17:00:00Z',
    request_id: 'e2e-request-team',
  },
]

export interface BusinessAuditApiState {
  auditRequests: number
  events: BusinessAuditEvent[]
}

function pageResponse(
  events: BusinessAuditEvent[],
  page: number,
  pageSize: number,
): BusinessAuditPageResponse {
  const totalEvents = events.length
  const totalPages = Math.ceil(totalEvents / pageSize)
  return {
    events: events.slice((page - 1) * pageSize, page * pageSize),
    page,
    page_size: pageSize,
    total_events: totalEvents,
    total_pages: totalPages,
    has_previous: page > 1,
    has_next: page < totalPages,
  }
}

function eventFromPlayerResponse(
  method: string,
  player: { id: string; first_name: string; last_name: string },
  sequence: number,
): BusinessAuditEvent {
  const created = method === 'POST'
  const label = `${player.first_name} ${player.last_name}`
  return {
    id: `00000000-0000-4000-8000-${String(300 + sequence).padStart(12, '0')}`,
    actor_user_id: actorId,
    actor_display_name: 'John Coach',
    actor_role: 'head coach',
    action_type: created ? 'player.created' : 'player.updated',
    action_category: 'player',
    target_entity_type: 'player',
    target_entity_id: player.id,
    target_label: label,
    summary: created
      ? `John Coach added ${label}`
      : `John Coach updated ${label}`,
    metadata: created ? {} : { changed_fields: ['bio'] },
    created_at: `2026-08-07T18:${String(sequence).padStart(2, '0')}:00Z`,
    request_id: `e2e-request-player-${sequence}`,
  }
}

/**
 * Install the stateful business-audit read API and observe successful player
 * mutations from the existing player E2E mock as externally initiated events.
 */
export async function installBusinessAuditApiMock(
  page: Page,
): Promise<BusinessAuditApiState> {
  const state: BusinessAuditApiState = {
    auditRequests: 0,
    events: structuredClone(initialEvents),
  }

  page.on('response', async (response) => {
    const request = response.request()
    const { pathname } = new URL(request.url())
    if (
      response.status() >= 400
      || !(/^\/api\/v1\/players(?:\/[^/]+)?$/.test(pathname))
      || !['POST', 'PUT'].includes(request.method())
    ) {
      return
    }
    const player = (await response.json()) as {
      id: string
      first_name: string
      last_name: string
    }
    const event = eventFromPlayerResponse(
      request.method(),
      player,
      state.events.length + 1,
    )
    state.events.unshift(event)
  })

  await page.route('**/api/v1/audit-log**', async (route) => {
    state.auditRequests += 1
    const url = new URL(route.request().url())
    const { pathname, searchParams } = url
    const ordered = [...state.events].sort(
      (left, right) =>
        right.created_at.localeCompare(left.created_at)
        || right.id.localeCompare(left.id),
    )

    if (pathname === '/api/v1/audit-log/recent') {
      const limit = Number(searchParams.get('limit') ?? 4)
      await route.fulfill({ status: 200, json: { events: ordered.slice(0, limit) } })
      return
    }

    if (pathname === '/api/v1/audit-log/actors') {
      await route.fulfill({
        status: 200,
        json: {
          actors: [
            {
              actor_user_id: actorId,
              actor_display_name: 'John Coach',
              actor_role: 'head coach',
            },
          ],
        },
      })
      return
    }

    if (pathname === '/api/v1/audit-log') {
      const filtered = ordered.filter((event) => {
        const category = searchParams.get('action_category')
        const action = searchParams.get('action_type')
        const entity = searchParams.get('entity_type')
        const actor = searchParams.get('actor_user_id')
        return (
          (category === null || event.action_category === category)
          && (action === null || event.action_type === action)
          && (entity === null || event.target_entity_type === entity)
          && (actor === null || event.actor_user_id === actor)
        )
      })
      const pageNumber = Number(searchParams.get('page') ?? 1)
      const pageSize = Number(searchParams.get('page_size') ?? 20)
      await route.fulfill({
        status: 200,
        json: pageResponse(filtered, pageNumber, pageSize),
      })
      return
    }

    await route.fallback()
  })

  return state
}
