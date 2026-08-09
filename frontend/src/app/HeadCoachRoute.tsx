import type { PropsWithChildren } from 'react'
import { useAuth } from '@features/auth'
import ForbiddenPage from '@/pages/ForbiddenPage'

interface HeadCoachRouteProps extends PropsWithChildren {
  forbiddenTitle?: string
  forbiddenDescription?: string
}

export default function HeadCoachRoute({
  children,
  forbiddenTitle = 'Audit Log is available to Head Coaches only.',
  forbiddenDescription = 'Your account does not have access to recorded academy activity.',
}: HeadCoachRouteProps) {
  const { user } = useAuth()

  if (user?.role !== 'head coach') {
    return (
      <ForbiddenPage
        title={forbiddenTitle}
        description={forbiddenDescription}
      />
    )
  }

  return children
}
