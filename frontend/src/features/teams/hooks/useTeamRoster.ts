import { useEffect, useState } from 'react'
import { isAbortError } from '@shared/api/errors'
import { fetchTeamRoster } from '../api/teamApi'
import type { TeamRosterResponse } from '../types/team'

export default function useTeamRoster(teamId: string | null) {
  const [roster, setRoster] = useState<TeamRosterResponse | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    if (teamId === null) {
      return
    }
    const controller = new AbortController()
    void fetchTeamRoster(teamId, controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) setRoster(response)
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && !isAbortError(error)) {
          setErrorMessage('Unable to load this team roster. Please try again.')
        }
      })
    return () => controller.abort()
  }, [retryKey, teamId])

  const isLoading = teamId !== null && roster?.team_id !== teamId && errorMessage === null
  function retry() {
    setErrorMessage(null)
    setRetryKey((key) => key + 1)
  }

  return { errorMessage, isLoading, retry, roster }
}
