import type { Page } from '@playwright/test'
import type { BusinessAuditApiState } from './audit-log-fixtures'
import type {
  DataQualityFinding,
  DataQualityPageResponse,
  DataQualityRemediationRequest,
} from '@features/data-quality/api/dataQualityApi'

const coachId = '00000000-0000-4000-8000-000000000301'
const teamId = '00000000-0000-4000-8000-000000000401'

const initialFindings: DataQualityFinding[] = [
  {
    finding_id: 'coach.sole_head_coach_integrity:academy',
    rule_id: 'coach.sole_head_coach_integrity',
    severity: 'critical',
    domain: 'coaches',
    entity_type: 'academy',
    entity_id: null,
    entity_label: 'Academy Head Coach coverage',
    title: 'Head Coach coverage requires review',
    explanation:
      'The academy cannot demonstrate one active Head Coach assignment for every current team.',
    recommended_action:
      'Review the Head Coach account and team assignments in Coaches Portal.',
    direct_remediation: null,
    related_entities: [],
  },
  {
    finding_id: 'player.active_unassigned:00000000-0000-4000-8000-000000000201',
    rule_id: 'player.active_unassigned',
    severity: 'warning',
    domain: 'players',
    entity_type: 'player',
    entity_id: '00000000-0000-4000-8000-000000000201',
    entity_label: 'Maya Patel',
    title: 'Active player is not assigned to a team',
    explanation:
      'Maya Patel is active but does not currently belong to a team roster.',
    recommended_action: 'Review Maya Patel in the Player Directory.',
    direct_remediation: null,
    related_entities: [],
  },
  {
    finding_id: `coach.inactive_assigned:${coachId}:${teamId}`,
    rule_id: 'coach.inactive_assigned',
    severity: 'warning',
    domain: 'coaches',
    entity_type: 'coach_assignment',
    entity_id: coachId,
    entity_label: 'Alex Morgan — U13 Falcons',
    title: 'Inactive Assistant Coach remains assigned',
    explanation:
      'Alex Morgan is inactive but remains assigned to U13 Falcons.',
    recommended_action:
      'Remove this one Assistant Coach assignment after confirmation.',
    direct_remediation: {
      action: 'remove_inactive_assistant_assignment',
      coach_id: coachId,
      team_id: teamId,
      expected_coach_version: 4,
      confirmation_required: true,
    },
    related_entities: [
      {
        entity_type: 'team',
        entity_id: teamId,
        entity_label: 'U13 Falcons',
      },
    ],
  },
  {
    finding_id: 'coach.active_assistant_unassigned:00000000-0000-4000-8000-000000000302',
    rule_id: 'coach.active_assistant_unassigned',
    severity: 'info',
    domain: 'coaches',
    entity_type: 'coach',
    entity_id: '00000000-0000-4000-8000-000000000302',
    entity_label: 'Priya Shah',
    title: 'Active Assistant Coach has no team assignment',
    explanation:
      'Priya Shah is active but does not currently have a team assignment.',
    recommended_action: 'Review assignments in Coaches Portal.',
    direct_remediation: null,
    related_entities: [],
  },
]

export interface DataQualityApiState {
  assignmentPresent: boolean
  qualityRequests: number
  remediationRequests: DataQualityRemediationRequest[]
}

function currentFindings(state: DataQualityApiState) {
  return state.assignmentPresent
    ? initialFindings
    : initialFindings.filter(
        (finding) => finding.rule_id !== 'coach.inactive_assigned',
      )
}

function responseFor(
  findings: DataQualityFinding[],
  searchParams: URLSearchParams,
): DataQualityPageResponse {
  const domainCounts = {
    players: 0,
    teams: 0,
    rosters: 0,
    coaches: 0,
    calendar: 0,
  }
  for (const finding of findings) domainCounts[finding.domain] += 1
  const summary = {
    total_findings: findings.length,
    critical_count: findings.filter((item) => item.severity === 'critical').length,
    warning_count: findings.filter((item) => item.severity === 'warning').length,
    info_count: findings.filter((item) => item.severity === 'info').length,
    domain_counts: domainCounts,
  }
  const filtered = findings.filter((finding) => {
    const severity = searchParams.get('severity')
    const domain = searchParams.get('domain')
    const ruleId = searchParams.get('rule_id')
    return (
      (severity === null || finding.severity === severity)
      && (domain === null || finding.domain === domain)
      && (ruleId === null || finding.rule_id === ruleId)
    )
  })
  const page = Number(searchParams.get('page') ?? 1)
  const pageSize = Number(searchParams.get('page_size') ?? 20)
  const totalPages = Math.ceil(filtered.length / pageSize)
  return {
    findings: filtered.slice((page - 1) * pageSize, page * pageSize),
    summary,
    page,
    page_size: pageSize,
    total_findings: filtered.length,
    total_pages: totalPages,
    has_previous: page > 1,
    has_next: page < totalPages,
  }
}

function recordAssignmentAudit(audit: BusinessAuditApiState) {
  audit.events.unshift({
    id: '00000000-0000-4000-8000-000000000501',
    actor_user_id: '550e8400-e29b-41d4-a716-446655440000',
    actor_display_name: 'John Coach',
    actor_role: 'head coach',
    action_type: 'coach.team_assignments_updated',
    action_category: 'coach',
    target_entity_type: 'coach',
    target_entity_id: coachId,
    target_label: 'Alex Morgan',
    summary: 'John Coach updated team assignments for Alex Morgan',
    metadata: { removed_team_ids: [teamId] },
    created_at: '2026-08-08T18:00:00Z',
    request_id: 'e2e-request-data-quality',
  })
}

export async function installDataQualityApiMock(
  page: Page,
  audit: BusinessAuditApiState,
): Promise<DataQualityApiState> {
  const state: DataQualityApiState = {
    assignmentPresent: true,
    qualityRequests: 0,
    remediationRequests: [],
  }

  await page.route('**/api/v1/data-quality**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (
      url.pathname === '/api/v1/data-quality/remediations'
      && request.method() === 'POST'
    ) {
      const command = request.postDataJSON() as DataQualityRemediationRequest
      state.remediationRequests.push(command)
      if (
        command.action !== 'remove_inactive_assistant_assignment'
        || command.finding_id !== `coach.inactive_assigned:${coachId}:${teamId}`
        || command.coach_id !== coachId
        || command.team_id !== teamId
        || command.expected_coach_version !== 4
        || command.confirmed !== true
        || !state.assignmentPresent
      ) {
        await route.fulfill({
          status: 409,
          json: { detail: 'The finding target or version changed.' },
        })
        return
      }
      state.assignmentPresent = false
      recordAssignmentAudit(audit)
      await route.fulfill({
        status: 200,
        json: {
          status: 'applied',
          action: command.action,
          message: 'The inactive Assistant Coach assignment was removed.',
          affected_entity_id: coachId,
          audit_action: 'coach.team_assignments_updated',
        },
      })
      return
    }

    if (url.pathname === '/api/v1/data-quality' && request.method() === 'GET') {
      state.qualityRequests += 1
      await route.fulfill({
        status: 200,
        json: responseFor(currentFindings(state), url.searchParams),
      })
      return
    }

    await route.fallback()
  })

  return state
}
