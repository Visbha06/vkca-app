import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'

export default function useInitialAddPlayerAction(canManagePlayers: boolean) {
  const [searchParams, setSearchParams] = useSearchParams()
  const shouldOpen = canManagePlayers && searchParams.get('action') === 'add'

  useEffect(() => {
    if (searchParams.get('action') !== 'add') return
    const nextParams = new URLSearchParams(searchParams)
    nextParams.delete('action')
    setSearchParams(nextParams, { replace: true })
  }, [searchParams, setSearchParams])

  return shouldOpen
}
