import type { PropsWithChildren } from 'react'
import { Navigate, useSearchParams } from 'react-router'
import { useAuth } from '../context/AuthContext'

function getRedirectTarget(redirect: string | null) {
  return redirect?.startsWith('/') && !redirect.startsWith('//') ? redirect : '/'
}

export default function GuestRoute({ children }: PropsWithChildren) {
  const { isAuthenticated, isInitializing } = useAuth()
  const [searchParams] = useSearchParams()

  if (isInitializing) return null

  if (isAuthenticated) {
    return (
      <Navigate
        replace
        to={getRedirectTarget(searchParams.get('redirect'))}
      />
    )
  }

  return children
}
