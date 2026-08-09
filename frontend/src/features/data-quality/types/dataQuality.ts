import type { components } from '../api/generated'

/** Request lifecycle state used only by the Data Quality interface. */
export type DataQualityRequestState =
  | 'idle'
  | 'loading'
  | 'refreshing'
  | 'success'
  | 'error'

/** Existing product workflow destinations used by review-only findings. */
export type DataQualityWorkflowPath =
  | '/players'
  | '/teams'
  | '/coaches'
  | '/calendar'

/** UI-owned filter state; API values remain derived from generated contracts. */
export interface DataQualityFiltersState {
  severity?: 'critical' | 'warning' | 'info'
  domain?: 'players' | 'teams' | 'rosters' | 'coaches' | 'calendar'
  ruleId?: components['schemas']['QualityRuleId']
}

/** Mutation lifecycle owned by the Data Quality page. */
export type DataQualityRemediationState =
  | 'idle'
  | 'submitting'
  | 'error'
  | 'conflict'

/** Result used by the page to close or retain its confirmation dialog. */
export type DataQualityRemediationOutcome =
  | 'applied'
  | 'conflict'
  | 'failed'
