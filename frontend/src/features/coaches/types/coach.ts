import type { UserRole } from '@features/auth/types/auth'

export type CoachStatusFilterValue = 'active' | 'inactive' | 'all'

export interface CoachTeamSummary {
  id: string
  name: string
}

export interface CoachResponse {
  id: string
  first_name: string
  last_name: string
  email: string
  role: Extract<UserRole, 'head coach' | 'assistant coach'>
  is_active: boolean
  version_number: number
  created_at: string
  updated_at: string
  teams: CoachTeamSummary[]
}

export interface PaginatedCoachResponse {
  coaches: CoachResponse[]
  page: number
  page_size: number
  total_coaches: number
  total_pages: number
  has_previous: boolean
  has_next: boolean
}

export interface CoachCreatePayload {
  first_name: string
  last_name: string
  email: string
  team_ids?: string[]
}

export interface CoachCreateResponse extends CoachResponse {
  temporary_password: string
}

export type CoachStatusResponse = Omit<CoachResponse, 'teams'>

export interface CoachTeamUpdatePayload {
  team_ids: string[]
  version_number: number
}
