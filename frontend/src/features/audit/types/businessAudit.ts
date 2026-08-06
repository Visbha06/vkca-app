export const BUSINESS_AUDIT_CATEGORIES = [
  'coach',
  'player',
  'team',
  'roster',
  'calendar',
] as const

export type BusinessAuditCategory =
  (typeof BUSINESS_AUDIT_CATEGORIES)[number]

export const BUSINESS_AUDIT_ENTITY_TYPES = [
  'coach',
  'player',
  'team',
  'roster',
  'calendar_event',
  'recurrence_series',
] as const

export type BusinessAuditEntityType =
  (typeof BUSINESS_AUDIT_ENTITY_TYPES)[number]

export const BUSINESS_AUDIT_ACTION_TYPES = [
  'coach.created',
  'coach.activated',
  'coach.deactivated',
  'coach.team_assignments_updated',
  'player.created',
  'player.updated',
  'team.created',
  'team.updated',
  'roster.added',
  'roster.removed',
  'roster.reordered',
  'calendar.standalone_created',
  'calendar.standalone_updated',
  'calendar.standalone_deleted',
  'calendar.series_created',
  'calendar.series_updated',
  'calendar.series_deleted',
  'calendar.occurrence_updated',
  'calendar.occurrence_moved',
  'calendar.occurrence_deleted',
] as const

export type BusinessAuditActionType =
  (typeof BUSINESS_AUDIT_ACTION_TYPES)[number]

export type BusinessAuditMetadataScalar =
  | string
  | number
  | boolean
  | null

export interface SafeBusinessAuditMetadata {
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
}

export interface BusinessAuditEvent {
  id: string
  actor_user_id: string | null
  actor_display_name: string | null
  actor_role: string | null
  action_type: BusinessAuditActionType
  action_category: BusinessAuditCategory
  target_entity_type: BusinessAuditEntityType
  target_entity_id: string | null
  target_label: string | null
  summary: string
  metadata: SafeBusinessAuditMetadata
  created_at: string
  request_id: string | null
}

export interface BusinessAuditPageResponse {
  events: BusinessAuditEvent[]
  page: number
  page_size: number
  total_events: number
  total_pages: number
  has_previous: boolean
  has_next: boolean
}

export interface RecentBusinessAuditResponse {
  events: BusinessAuditEvent[]
}

export interface BusinessAuditActorOption {
  actor_user_id: string
  actor_display_name: string
  actor_role: string | null
}

export interface BusinessAuditActorOptionsResponse {
  actors: BusinessAuditActorOption[]
}

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
