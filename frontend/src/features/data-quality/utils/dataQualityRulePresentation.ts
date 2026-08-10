import type { components } from '../api/generated'

type QualityRuleId = components['schemas']['QualityRuleId']
type QualityDomain = components['schemas']['QualityDomain']

interface DataQualityRulePresentation {
  label: string
  domain: QualityDomain
}

export const DATA_QUALITY_RULE_PRESENTATION = {
  'player.active_unassigned': {
    label: 'Active player without a team',
    domain: 'players',
  },
  'player.inactive_rostered': {
    label: 'Inactive player still on a roster',
    domain: 'players',
  },
  'player.normalized_identity_duplicate': {
    label: 'Possible duplicate player',
    domain: 'players',
  },
  'team.roster_below_minimum': {
    label: 'Team below minimum roster size',
    domain: 'teams',
  },
  'team.roster_above_maximum': {
    label: 'Team above maximum roster size',
    domain: 'teams',
  },
  'roster.order_non_positive': {
    label: 'Roster position is zero or below',
    domain: 'rosters',
  },
  'roster.order_duplicate': {
    label: 'Duplicate roster position',
    domain: 'rosters',
  },
  'roster.order_gap': {
    label: 'Gap in roster order',
    domain: 'rosters',
  },
  'roster.order_non_contiguous': {
    label: 'Roster order does not start at 1',
    domain: 'rosters',
  },
  'team.normalized_name_conflict': {
    label: 'Duplicate team name in age group',
    domain: 'teams',
  },
  'team.no_assigned_coach': {
    label: 'Team has no assigned coach',
    domain: 'teams',
  },
  'coach.sole_head_coach_integrity': {
    label: 'Head Coach coverage needs review',
    domain: 'coaches',
  },
  'coach.inactive_assigned': {
    label: 'Inactive Assistant Coach still assigned',
    domain: 'coaches',
  },
  'coach.active_assistant_unassigned': {
    label: 'Assistant Coach without a team',
    domain: 'coaches',
  },
  'coach.assignment_invalid_role': {
    label: 'Team assignment uses a non-coach role',
    domain: 'coaches',
  },
  'calendar.recurrence_end_before_start': {
    label: 'Recurring event ends before it starts',
    domain: 'calendar',
  },
  'calendar.stale_occurrence_exception': {
    label: 'Saved occurrence change no longer matches',
    domain: 'calendar',
  },
} satisfies Record<QualityRuleId, DataQualityRulePresentation>

export const DATA_QUALITY_RULE_GROUPS = [
  { domain: 'players', label: 'Players' },
  { domain: 'teams', label: 'Teams' },
  { domain: 'rosters', label: 'Rosters' },
  { domain: 'coaches', label: 'Coaches' },
  { domain: 'calendar', label: 'Calendar' },
] as const satisfies readonly { domain: QualityDomain; label: string }[]

export function getDataQualityRulesForDomain(domain: QualityDomain) {
  return (Object.entries(DATA_QUALITY_RULE_PRESENTATION) as [
    QualityRuleId,
    DataQualityRulePresentation,
  ][]).filter(([, presentation]) => presentation.domain === domain)
}
