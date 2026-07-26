import { useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import AccountSettingsModal from '../components/AccountSettingsModal'

function getReturnPath(state: unknown) {
  if (
    typeof state === 'object' &&
    state !== null &&
    'from' in state &&
    typeof state.from === 'string' &&
    state.from.startsWith('/') &&
    !state.from.startsWith('//') &&
    state.from !== '/settings'
  ) {
    return state.from
  }

  return '/'
}

export default function SettingsPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const returnPath = getReturnPath(location.state)
  const handleClose = useCallback(() => {
    navigate(returnPath, { replace: true })
  }, [navigate, returnPath])

  return <AccountSettingsModal onClose={handleClose} />
}
