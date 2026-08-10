import type { DataQualityFinding } from '../api/dataQualityApi'
import type { DataQualityWorkflowPath } from '../types/dataQuality'

const workflowTargets: Record<
  DataQualityFinding['rule_id'],
  DataQualityWorkflowPath
> = {
  'player.active_unassigned': '/players',
  'player.inactive_rostered': '/teams',
  'player.normalized_identity_duplicate': '/players',
  'team.roster_below_minimum': '/teams',
  'team.roster_above_maximum': '/teams',
  'roster.order_non_positive': '/teams',
  'roster.order_duplicate': '/teams',
  'roster.order_gap': '/teams',
  'roster.order_non_contiguous': '/teams',
  'team.normalized_name_conflict': '/teams',
  'team.no_assigned_coach': '/coaches',
  'coach.sole_head_coach_integrity': '/coaches',
  'coach.inactive_assigned': '/coaches',
  'coach.active_assistant_unassigned': '/coaches',
  'coach.assignment_invalid_role': '/coaches',
  'calendar.recurrence_end_before_start': '/calendar',
  'calendar.stale_occurrence_exception': '/calendar',
}

const manualReviewRules = new Set<DataQualityFinding['rule_id']>([
  'coach.sole_head_coach_integrity',
  'coach.assignment_invalid_role',
])

export function getWorkflowTarget(ruleId: DataQualityFinding['rule_id']) {
  return workflowTargets[ruleId]
}

export function requiresManualReview(ruleId: DataQualityFinding['rule_id']) {
  return manualReviewRules.has(ruleId)
}
