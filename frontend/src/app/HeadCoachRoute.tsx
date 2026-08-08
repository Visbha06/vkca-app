import type { PropsWithChildren } from 'react'
import { useAuth } from '@features/auth'
import ForbiddenPage from '@/pages/ForbiddenPage'

export default function HeadCoachRoute({ children }: PropsWithChildren) {
  const { user } = useAuth()

  if (user?.role !== 'head coach') {
    return (
      <ForbiddenPage
        title="Audit Log is available to Head Coaches only."
        description="Your account does not have access to recorded academy activity."
      />
    )
  }

  return children
}
