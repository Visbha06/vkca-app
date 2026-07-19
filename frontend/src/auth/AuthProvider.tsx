import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  type PropsWithChildren,
} from 'react'
import { apiClient } from '../api/client'
import { AuthContext, type AuthContextValue } from './AuthContext'
import type {
  AuthState,
  AuthUser,
  LoginCredentials,
  LoginResponse,
  RefreshResponse,
} from './types'

const LOGIN_PATH = '/api/v1/auth/login'
const LOGOUT_PATH = '/api/v1/auth/logout'
const ME_PATH = '/api/v1/auth/me'
const REFRESH_PATH = '/api/v1/auth/refresh'

const initialState: AuthState = {
  user: null,
  accessToken: null,
  isAuthenticated: false,
  isInitializing: true,
  isLoginPending: false,
  isLogoutPending: false,
}

type AuthAction =
  | { type: 'loginStarted' }
  | { type: 'loginFailed' }
  | { type: 'logoutStarted' }
  | { type: 'authenticated'; user: AuthUser; accessToken: string }
  | { type: 'userUpdated'; user: AuthUser }
  | { type: 'accessTokenRefreshed'; accessToken: string }
  | { type: 'authenticationCleared' }
  | { type: 'initializationFinished' }

function authReducer(state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case 'loginStarted':
      return { ...state, isLoginPending: true }
    case 'loginFailed':
      return { ...state, isLoginPending: false }
    case 'logoutStarted':
      return { ...state, isLogoutPending: true }
    case 'authenticated':
      return {
        ...state,
        user: action.user,
        accessToken: action.accessToken,
        isAuthenticated: true,
        isLoginPending: false,
        isLogoutPending: false,
      }
    case 'userUpdated':
      return state.user === null ? state : { ...state, user: action.user }
    case 'accessTokenRefreshed':
      return state.isAuthenticated
        ? { ...state, accessToken: action.accessToken }
        : state
    case 'authenticationCleared':
      return {
        ...state,
        user: null,
        accessToken: null,
        isAuthenticated: false,
        isLoginPending: false,
        isLogoutPending: false,
      }
    case 'initializationFinished':
      return { ...state, isInitializing: false }
  }
}

export default function AuthProvider({ children }: PropsWithChildren) {
  const [state, dispatch] = useReducer(authReducer, initialState)
  const restoreStarted = useRef(false)

  const clearAuthentication = useCallback(() => {
    apiClient.setAccessToken(null)
    dispatch({ type: 'authenticationCleared' })
  }, [])

  const authenticateWithToken = useCallback(async (accessToken: string) => {
    apiClient.setAccessToken(accessToken)

    try {
      const user = await apiClient.request<AuthUser>(ME_PATH)
      dispatch({
        type: 'authenticated',
        user,
        accessToken: apiClient.getAccessToken() ?? accessToken,
      })
    } catch (error) {
      clearAuthentication()
      throw error
    }
  }, [clearAuthentication])

  const login = useCallback(
    async (email: string, password: string) => {
      dispatch({ type: 'loginStarted' })

      try {
        const credentials: LoginCredentials = { email, password }
        const response = await apiClient.request<LoginResponse>(LOGIN_PATH, {
          method: 'POST',
          body: JSON.stringify(credentials),
        })
        await authenticateWithToken(response.access_token)
      } catch (error) {
        dispatch({ type: 'loginFailed' })
        throw error
      }
    },
    [authenticateWithToken],
  )

  const logout = useCallback(async () => {
    dispatch({ type: 'logoutStarted' })

    try {
      await apiClient.request<void>(LOGOUT_PATH, { method: 'POST' })
    } catch {
      // Local authentication is cleared even when session revocation fails.
    } finally {
      clearAuthentication()
    }
  }, [clearAuthentication])

  const refreshSession = useCallback(async () => {
    try {
      const response = await apiClient.request<RefreshResponse>(REFRESH_PATH, {
        method: 'POST',
      })
      await authenticateWithToken(response.access_token)
      return true
    } catch {
      clearAuthentication()
      return false
    }
  }, [authenticateWithToken, clearAuthentication])

  const updateUser = useCallback((user: AuthUser) => {
    dispatch({ type: 'userUpdated', user })
  }, [])

  useEffect(() => {
    apiClient.setAuthHandlers({
      onAccessTokenRefreshed: (accessToken) => {
        dispatch({ type: 'accessTokenRefreshed', accessToken })
      },
      onSessionExpired: clearAuthentication,
    })

    return () => apiClient.setAuthHandlers(null)
  }, [clearAuthentication])

  useEffect(() => {
    if (restoreStarted.current) {
      return
    }

    restoreStarted.current = true
    void refreshSession().finally(() => {
      dispatch({ type: 'initializationFinished' })
    })
  }, [refreshSession])

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      login,
      logout,
      refreshSession,
      updateUser,
    }),
    [state, login, logout, refreshSession, updateUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
