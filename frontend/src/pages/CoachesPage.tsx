import { useAuth } from '@features/auth'
import { CoachesPage as CoachesFeaturePage } from '@features/coaches'
import ForbiddenPage from './ForbiddenPage'

export default function CoachesPage() {
  const { user } = useAuth()

  return user?.role === 'player' ? <ForbiddenPage /> : <CoachesFeaturePage />
}
