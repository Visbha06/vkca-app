// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
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
})
