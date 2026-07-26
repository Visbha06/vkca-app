import { apiClient } from '@shared/api/client'
import type {
  AuthUser,
  LoginCredentials,
  LoginResponse,
  RefreshResponse,
} from '../types/auth'

const LOGIN_PATH = '/api/v1/auth/login'
const LOGOUT_PATH = '/api/v1/auth/logout'
const ME_PATH = '/api/v1/auth/me'
const REFRESH_PATH = '/api/v1/auth/refresh'

export function loginWithCredentials(credentials: LoginCredentials) {
  return apiClient.request<LoginResponse>(LOGIN_PATH, {
    method: 'POST',
    body: JSON.stringify(credentials),
  })
}

export function logoutSession() {
  return apiClient.request<void>(LOGOUT_PATH, { method: 'POST' })
}

export function fetchCurrentUser() {
  return apiClient.request<AuthUser>(ME_PATH)
}

export function refreshAuthSession() {
  return apiClient.request<RefreshResponse>(REFRESH_PATH, { method: 'POST' })
}
