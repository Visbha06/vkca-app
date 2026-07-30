import { useEffect, useRef, useState } from 'react'
import { fetchCoaches } from '../api/coachApi'
import type {
  CoachResponse,
  CoachStatusFilterValue,
  PaginatedCoachResponse,
} from '../types/coach'

const PAGE_SIZE = 12

function matchesStatus(
  coach: CoachResponse,
  status: CoachStatusFilterValue,
) {
  return (
    status === 'all' ||
    (status === 'active' ? coach.is_active : !coach.is_active)
  )
}

function compareCoaches(left: CoachResponse, right: CoachResponse) {
  const roleOrder =
    Number(left.role !== 'head coach') - Number(right.role !== 'head coach')
  if (roleOrder !== 0) return roleOrder
  return (
    left.last_name.localeCompare(right.last_name) ||
    left.first_name.localeCompare(right.first_name) ||
    left.id.localeCompare(right.id)
  )
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError'
}

export default function useCoachDirectory() {
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState<CoachStatusFilterValue>('active')
  const [result, setResult] = useState<PaginatedCoachResponse | null>(null)
  const [isFetching, setIsFetching] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const listRegionRef = useRef<HTMLDivElement>(null)
  const focusListAfterLoadRef = useRef(false)

  useEffect(() => {
    const controller = new AbortController()
    void fetchCoaches({ status, page, pageSize: PAGE_SIZE }, controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) {
          setResult(response)
          setErrorMessage(null)
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && !isAbortError(error)) {
          setErrorMessage('Unable to load coaches. Please try again.')
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsFetching(false)
      })
    return () => controller.abort()
  }, [page, retryKey, status])

  useEffect(() => {
    if (!isFetching && focusListAfterLoadRef.current) {
      focusListAfterLoadRef.current = false
      listRegionRef.current?.focus()
    }
  }, [isFetching])

  function handleFilterChange(nextStatus: CoachStatusFilterValue) {
    setIsFetching(true)
    setErrorMessage(null)
    setStatus(nextStatus)
    setPage(1)
  }

  function handlePageChange(nextPage: number) {
    if (nextPage === page || nextPage < 1) return
    focusListAfterLoadRef.current = true
    setIsFetching(true)
    setErrorMessage(null)
    setPage(nextPage)
  }

  function handleRetry() {
    setIsFetching(true)
    setErrorMessage(null)
    setRetryKey((key) => key + 1)
  }

  function handleCoachCreated(coach: CoachResponse) {
    setResult((current) => {
      if (current === null) return current
      const totalCoaches = current.total_coaches + 1
      const totalPages = Math.ceil(totalCoaches / current.page_size)
      const coaches =
        current.page === 1 && matchesStatus(coach, status)
          ? [...current.coaches, coach]
              .sort(compareCoaches)
              .slice(0, current.page_size)
          : current.coaches
      return {
        ...current,
        coaches,
        total_coaches: totalCoaches,
        total_pages: totalPages,
        has_next: current.page < totalPages,
      }
    })
    setSuccessMessage(
      `${coach.first_name} ${coach.last_name} was added successfully.`,
    )
  }

  function updateCoachInDirectory(
    coach: CoachResponse,
    announceStatus: boolean,
  ) {
    setResult((current) => {
      if (current === null) return current
      const coachIndex = current.coaches.findIndex(
        (candidate) => candidate.id === coach.id,
      )
      if (coachIndex < 0) return current
      const remainsVisible = matchesStatus(coach, status)
      const coaches = remainsVisible
        ? current.coaches
            .map((candidate) =>
              candidate.id === coach.id ? coach : candidate,
            )
            .sort(compareCoaches)
        : current.coaches.filter((candidate) => candidate.id !== coach.id)
      const totalCoaches = remainsVisible
        ? current.total_coaches
        : Math.max(0, current.total_coaches - 1)
      const totalPages = Math.ceil(totalCoaches / current.page_size)
      return {
        ...current,
        coaches,
        total_coaches: totalCoaches,
        total_pages: totalPages,
        has_next: current.page < totalPages,
      }
    })
    if (announceStatus) {
      setSuccessMessage(
        `${coach.first_name} ${coach.last_name} is now ${
          coach.is_active ? 'active' : 'inactive'
        }.`,
      )
    }
  }

  return {
    errorMessage,
    handleCoachCreated,
    handleCoachReloaded: (coach: CoachResponse) =>
      updateCoachInDirectory(coach, false),
    handleCoachStatusChanged: (coach: CoachResponse) =>
      updateCoachInDirectory(coach, true),
    handleFilterChange,
    handlePageChange,
    handleRetry,
    isFetching,
    listRegionRef,
    result,
    status,
    successMessage,
  }
}
