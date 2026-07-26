export type AgeGroup = 'J' | 'U11' | 'U13' | 'U15'

export interface TeamResponse {
  id: string
  name: string
  age_group: AgeGroup
  player_count: number
  created_at: string
  updated_at: string
  version_number: number
}

export interface PaginatedTeamResponse {
  teams: TeamResponse[]
  page: number
  page_size: number
  total_teams: number
  total_pages: number
}

export interface TeamCreatePayload {
  name: string
  age_group: AgeGroup
  player_ids: string[]
}

export interface TeamUpdatePayload extends TeamCreatePayload {
  version_number: number
}

export interface TeamRosterPlayerResponse {
  player_id: string
  first_name: string
  last_name: string
  is_active: boolean
  roster_order: number
}

export interface TeamRosterResponse {
  team_id: string
  players: TeamRosterPlayerResponse[]
}
