import type { PropsWithChildren } from 'react'
import { Navigate, useLocation } from 'react-router'
import { useAuth } from '../context/AuthContext'

export default function ProtectedRoute({ children }: PropsWithChildren) {
  const { isAuthenticated, isInitializing } = useAuth()
  const location = useLocation()

  if (isInitializing) return null

  if (!isAuthenticated) {
    const requestedPath = `${location.pathname}${location.search}${location.hash}`
    return (
      <Navigate
        replace
        to={`/login?redirect=${encodeURIComponent(requestedPath)}`}
      />
    )
  }

  return children
}
