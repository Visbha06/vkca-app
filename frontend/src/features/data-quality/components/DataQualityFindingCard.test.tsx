// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import DataQualityFindingCard from './DataQualityFindingCard'
import { getWorkflowTarget } from '../utils/dataQualityNavigation'

const ruleIds = [
  'player.active_unassigned', 'player.inactive_rostered', 'player.normalized_identity_duplicate',
  'team.roster_below_minimum', 'team.roster_above_maximum', 'roster.order_non_positive',
  'roster.order_duplicate', 'roster.order_gap', 'roster.order_non_contiguous',
  'team.normalized_name_conflict', 'team.no_assigned_coach', 'coach.sole_head_coach_integrity',
  'coach.inactive_assigned', 'coach.active_assistant_unassigned', 'coach.assignment_invalid_role',
  'calendar.recurrence_end_before_start', 'calendar.stale_occurrence_exception',
] as const

afterEach(() => cleanup())

describe('DataQualityFindingCard', () => {
  it.each(ruleIds)('maps %s to its existing review workflow', (ruleId) => {
    expect(getWorkflowTarget(ruleId)).toMatch(/^\/(players|teams|coaches|calendar)$/)
  })

  it('marks manual-review-only findings without offering an action', () => {
    render(<DataQualityFindingCard finding={{ finding_id: 'head', rule_id: 'coach.sole_head_coach_integrity', severity: 'critical', domain: 'coaches', entity_type: 'academy', entity_id: null, entity_label: 'Academy', title: 'Coverage needs review', explanation: 'Review required.', recommended_action: 'Review manually.', direct_remediation: null, related_entities: [] }} onNavigate={vi.fn()} />)

    expect(screen.getByText('Manual review required')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Navigate to Fix' })).not.toBeInTheDocument()
  })

  it('provides a deterministic navigate action for a reviewable finding', () => {
    const onNavigate = vi.fn()
    render(<DataQualityFindingCard finding={{ finding_id: 'player', rule_id: 'player.active_unassigned', severity: 'warning', domain: 'players', entity_type: 'player', entity_id: 'player', entity_label: 'Asha', title: 'Unassigned', explanation: 'Review.', recommended_action: 'Open Players.', direct_remediation: null, related_entities: [] }} onNavigate={onNavigate} />)

    fireEvent.click(screen.getByRole('button', { name: 'Navigate to Fix' }))
    expect(onNavigate).toHaveBeenCalledWith('/players', 'Asha')
  })

  it('shows only the API-provided direct remediation action', () => {
    const onRemediate = vi.fn()
    render(
      <DataQualityFindingCard
        finding={{
          finding_id: 'coach.inactive_assigned:coach:team',
          rule_id: 'coach.inactive_assigned',
          severity: 'warning',
          domain: 'coaches',
          entity_type: 'coach_assignment',
          entity_id: 'coach',
          entity_label: 'Alex Morgan — U13 Falcons',
          title: 'Inactive Assistant Coach remains assigned',
          explanation: 'The inactive assignment remains current.',
          recommended_action: 'Remove this one assignment.',
          direct_remediation: {
            action: 'remove_inactive_assistant_assignment',
            coach_id: 'coach',
            team_id: 'team',
            expected_coach_version: 4,
            confirmation_required: true,
          },
          related_entities: [],
        }}
        onNavigate={vi.fn()}
        onRemediate={onRemediate}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Remove assignment' }))
    expect(onRemediate).toHaveBeenCalledWith(
      expect.objectContaining({
        finding_id: 'coach.inactive_assigned:coach:team',
      }),
    )
    expect(
      screen.queryByRole('button', { name: 'Navigate to Fix' }),
    ).not.toBeInTheDocument()
  })
})
