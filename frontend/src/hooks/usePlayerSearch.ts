import { useEffect, useState } from 'react'
import { fetchPlayers } from '../api/playerApi'
import type { PlayerResponse } from '../types/player'

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError'
}

export default function usePlayerSearch(
  query: string,
  isOpen: boolean,
  disabled: boolean,
) {
  const [results, setResults] = useState<PlayerResponse[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    if (!isOpen || disabled) return
    const controller = new AbortController()
    const normalizedQuery = query.trim()
    const timer = window.setTimeout(() => {
      setIsLoading(true)
      setErrorMessage(null)
      void fetchPlayers(
        {
          page: 1,
          pageSize: 50,
          ...(normalizedQuery === '' ? {} : { search: normalizedQuery }),
        },
        controller.signal,
      )
        .then((response) => {
          if (!controller.signal.aborted) setResults(response.players)
        })
        .catch((error: unknown) => {
          if (!controller.signal.aborted && !isAbortError(error)) {
            setErrorMessage('Unable to search players.')
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) setIsLoading(false)
        })
    }, retryKey === 0 ? 300 : 0)

    return () => {
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [disabled, isOpen, query, retryKey])

  return {
    errorMessage,
    isLoading,
    results,
    retry: () => setRetryKey((key) => key + 1),
  }
}
