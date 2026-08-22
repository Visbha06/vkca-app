export type UserRole = 'head coach' | 'assistant coach' | 'player'

export interface SessionMeta {
  session_id: string
  created_at: string
  last_used_at: string
  expires_at: string
}

export interface AuthUser {
  id: string
  first_name: string
  last_name: string
  email: string
  role: UserRole
  is_active: boolean
  created_at: string
  updated_at: string
  session: SessionMeta
}

export interface AuthState {
  user: AuthUser | null
  isAuthenticated: boolean
  isInitializing: boolean
  isLoginPending: boolean
  isLogoutPending: boolean
}

export interface LoginCredentials {
  email: string
  password: string
}

export interface ProfileUpdateRequest {
  first_name: string
  last_name: string
}

export interface PasswordChangeRequest {
  new_password: string
  confirm_password: string
}

export interface ApiError {
  detail: string
}

export interface LoginResponse {
  access_token: string
  token_type: 'bearer'
}

export interface RefreshResponse {
  access_token: string
  token_type: 'bearer'
}
