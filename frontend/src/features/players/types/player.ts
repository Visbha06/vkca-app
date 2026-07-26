export type BattingStyle = 'right' | 'left'

export type BowlingStyle =
  | 'right-arm fast'
  | 'right-arm medium'
  | 'right-arm off-break'
  | 'right-arm leg-break'
  | 'left-arm fast'
  | 'left-arm medium'
  | 'left-arm orthodox'
  | 'left-arm unorthodox'

export type PlayerType =
  | 'batter'
  | 'bowler'
  | 'all-rounder'
  | 'wicket-keeper'

export interface TeamSummary {
  id: string
  name: string
}

export interface PlayerResponse {
  id: string
  first_name: string
  last_name: string
  date_of_birth: string
  bio: string | null
  batting_style: BattingStyle
  bowling_style: BowlingStyle
  player_type: PlayerType
  player_metadata: Record<string, unknown>
  is_active: boolean
  created_at: string
  updated_at: string
  version_number: number
  teams: TeamSummary[]
}

export interface PaginatedPlayerResponse {
  players: PlayerResponse[]
  page: number
  page_size: number
  total_players: number
  total_pages: number
  has_previous: boolean
  has_next: boolean
}

export interface PlayerCreatePayload {
  first_name: string
  last_name: string
  date_of_birth: string
  bio?: string | null
  batting_style: BattingStyle
  bowling_style: BowlingStyle
  player_type: PlayerType
  player_metadata?: Record<string, unknown>
}

export interface PlayerUpdatePayload {
  first_name?: string
  last_name?: string
  date_of_birth?: string
  bio?: string | null
  batting_style?: BattingStyle
  bowling_style?: BowlingStyle
  player_type?: PlayerType
  player_metadata?: Record<string, unknown>
  is_active?: boolean
  version_number: number
}
