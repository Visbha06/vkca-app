import type { components } from '../api/generated'

export type BusinessAuditCategory =
  components['schemas']['AuditActionCategory']

export const BUSINESS_AUDIT_CATEGORIES = [
  'coach',
  'player',
  'team',
  'roster',
  'calendar',
  'scoring',
] as const satisfies readonly BusinessAuditCategory[]

export type BusinessAuditEntityType =
  components['schemas']['AuditEntityType']

export const BUSINESS_AUDIT_ENTITY_TYPES = [
  'coach',
  'player',
  'team',
  'roster',
  'calendar_event',
  'recurrence_series',
  'match',
] as const satisfies readonly BusinessAuditEntityType[]

export type BusinessAuditActionType =
  components['schemas']['AuditActionType']

const BUSINESS_AUDIT_ACTION_ORDER = {
  'coach.created': true,
  'coach.activated': true,
  'coach.deactivated': true,
  'coach.team_assignments_updated': true,
  'player.created': true,
  'player.updated': true,
  'player.account_linked': true,
  'player.account_unlinked': true,
  'player.account_reassigned': true,
  'team.created': true,
  'team.updated': true,
  'roster.added': true,
  'roster.removed': true,
  'roster.reordered': true,
  'calendar.standalone_created': true,
  'calendar.standalone_updated': true,
  'calendar.standalone_deleted': true,
  'calendar.series_created': true,
  'calendar.series_updated': true,
  'calendar.series_deleted': true,
  'calendar.occurrence_updated': true,
  'calendar.occurrence_moved': true,
  'calendar.occurrence_deleted': true,
  'scoring.initialized': true,
} satisfies Record<BusinessAuditActionType, true>

export const BUSINESS_AUDIT_ACTION_TYPES = Object.keys(
  BUSINESS_AUDIT_ACTION_ORDER,
) as BusinessAuditActionType[]

export type BusinessAuditMetadataScalar =
  components['schemas']['BusinessAuditMetadataScalar']

type GeneratedBusinessAuditMetadata =
  components['schemas']['BusinessAuditEventResponse']['metadata']

export type SafeBusinessAuditMetadata = GeneratedBusinessAuditMetadata & {
  assigned_team_ids?: BusinessAuditMetadataScalar[]
  assigned_team_count?: number
  changed_fields?: BusinessAuditMetadataScalar[]
  added_team_ids?: BusinessAuditMetadataScalar[]
  removed_team_ids?: BusinessAuditMetadataScalar[]
  added_count?: number
  removed_count?: number
  age_group?: string
  roster_count?: number
  roster_replaced?: boolean
  added_player_ids?: BusinessAuditMetadataScalar[]
  removed_player_ids?: BusinessAuditMetadataScalar[]
  reordered_player_ids?: BusinessAuditMetadataScalar[]
  player_id?: string
  new_roster_position?: number
  prior_roster_position?: number
  affected_player_ids?: BusinessAuditMetadataScalar[]
  affected_count?: number
  changed_positions?: BusinessAuditMetadataScalar[]
  event_type?: string
  scope?: string
  schedule_label?: string
  frequency?: string
  exception_count?: number
  original_date?: string
  replacement_date?: string
  account_user_id?: string
  previous_account_user_id?: string
  capability_profile?: string
  capability_version?: number
  innings_sequence?: BusinessAuditMetadataScalar[]
  participant_count?: number
}

export interface BusinessAuditEvent
  extends Omit<
    components['schemas']['BusinessAuditEventResponse'],
    'metadata'
  > {
  metadata: SafeBusinessAuditMetadata
}

export interface BusinessAuditPageResponse
  extends Omit<
    components['schemas']['BusinessAuditPageResponse'],
    'events'
  > {
  events: BusinessAuditEvent[]
}

export interface RecentBusinessAuditResponse
  extends Omit<
    components['schemas']['RecentBusinessAuditResponse'],
    'events'
  > {
  events: BusinessAuditEvent[]
}

export type BusinessAuditActorOption =
  components['schemas']['BusinessAuditActorOption']

export type BusinessAuditActorOptionsResponse =
  components['schemas']['BusinessAuditActorOptionsResponse']

export interface BusinessAuditFilters {
  actorUserId?: string
  actionCategory?: BusinessAuditCategory
  actionType?: BusinessAuditActionType
  entityType?: BusinessAuditEntityType
  targetEntityId?: string
  startDate?: string
  endDate?: string
}

export interface BusinessAuditListParams extends BusinessAuditFilters {
  page?: number
  pageSize?: number
}
