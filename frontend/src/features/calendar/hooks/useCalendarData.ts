import { useCallback, useEffect, useRef, useState } from 'react'
import { isAbortError } from '@shared/api/errors'
import {
  fetchCalendarInstance,
  fetchCalendarRange,
  fetchCalendarToday,
} from '../api/calendarApi'
import { getCalendarErrorMessage } from '../utils/calendarErrors'
import {
  addCalendarMonths,
  calendarGridRange,
  calendarMonthFromDate,
  calendarDateToIso,
  parseAcademyDate,
  type CalendarDate,
  type CalendarMonth,
} from '@shared/utils/calendarDate'
import type {
  CalendarEventInstance,
  CalendarRangeResponse,
} from '../types/calendar'

function parseResponseDate(value: string): CalendarDate {
  const parsed = parseAcademyDate(value)
  if (parsed === null) throw new Error('The calendar returned an invalid date.')
  return parsed
}

export default function useCalendarData() {
  const [academyToday, setAcademyToday] = useState<string | null>(null)
  const [viewMonth, setViewMonth] = useState<CalendarMonth | null>(null)
  const [focusedDate, setFocusedDate] = useState<CalendarDate | null>(null)
  const [events, setEvents] = useState<CalendarEventInstance[]>([])
  const [todayEvents, setTodayEvents] = useState<CalendarEventInstance[]>([])
  const [selectedInstance, setSelectedInstance] =
    useState<CalendarEventInstance | null>(null)
  const [isDetailLoading, setIsDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [isTodayLoading, setIsTodayLoading] = useState(true)
  const [isRangeLoading, setIsRangeLoading] = useState(true)
  const [todayError, setTodayError] = useState<string | null>(null)
  const [rangeError, setRangeError] = useState<string | null>(null)
  const [todayRetryKey, setTodayRetryKey] = useState(0)
  const [rangeRetryKey, setRangeRetryKey] = useState(0)
  const todayRequestId = useRef(0)
  const rangeRequestId = useRef(0)
  const detailRequestId = useRef(0)
  const detailController = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    const requestId = todayRequestId.current + 1
    todayRequestId.current = requestId

    void fetchCalendarToday(controller.signal)
      .then((response) => {
        if (
          controller.signal.aborted ||
          todayRequestId.current !== requestId
        ) {
          return
        }
        const currentDate = parseResponseDate(response.academy_today)
        setAcademyToday(response.academy_today)
        setTodayEvents(response.events)
        setViewMonth((current) => current ?? calendarMonthFromDate(currentDate))
        setFocusedDate((current) => current ?? currentDate)
      })
      .catch((error: unknown) => {
        if (
          !controller.signal.aborted &&
          todayRequestId.current === requestId &&
          !isAbortError(error)
        ) {
          setIsRangeLoading(false)
          setTodayError(
            getCalendarErrorMessage(
              error,
              'Unable to load Today. Please try again.',
            ),
          )
        }
      })
      .finally(() => {
        if (
          !controller.signal.aborted &&
          todayRequestId.current === requestId
        ) {
          setIsTodayLoading(false)
        }
      })

    return () => controller.abort()
  }, [todayRetryKey])

  useEffect(
    () => () => {
      detailController.current?.abort()
    },
    [],
  )

  useEffect(() => {
    if (viewMonth === null) return
    const controller = new AbortController()
    const requestId = rangeRequestId.current + 1
    rangeRequestId.current = requestId
    const visibleRange = calendarGridRange(viewMonth)

    void fetchCalendarRange(
      {
        startDate: calendarDateToIso(visibleRange.earliest),
        endDate: calendarDateToIso(visibleRange.latest),
      },
      controller.signal,
    )
      .then((response: CalendarRangeResponse) => {
        if (controller.signal.aborted || rangeRequestId.current !== requestId) {
          return
        }
        setEvents(response.events)
      })
      .catch((error: unknown) => {
        if (
          !controller.signal.aborted &&
          rangeRequestId.current === requestId &&
          !isAbortError(error)
        ) {
          setRangeError(
            getCalendarErrorMessage(
              error,
              'Unable to load the calendar. Please try again.',
            ),
          )
        }
      })
      .finally(() => {
        if (
          !controller.signal.aborted &&
          rangeRequestId.current === requestId
        ) {
          setIsRangeLoading(false)
        }
      })

    return () => controller.abort()
  }, [rangeRetryKey, viewMonth])

  const navigateToMonth = useCallback(
    (nextMonth: CalendarMonth) => {
      setIsRangeLoading(true)
      setRangeError(null)
      setEvents([])
      setViewMonth((current) => {
        if (current === null) return nextMonth
        const currentFocusDay = focusedDate?.day ?? 1
        const next = addCalendarMonths({ ...nextMonth, day: currentFocusDay }, 0)
        setFocusedDate(next)
        return { year: next.year, month: next.month }
      })
    },
    [focusedDate],
  )

  const goToPreviousMonth = useCallback(() => {
    if (viewMonth === null) return
    navigateToMonth(addCalendarMonths({ ...viewMonth, day: 1 }, -1))
  }, [navigateToMonth, viewMonth])

  const goToNextMonth = useCallback(() => {
    if (viewMonth === null) return
    navigateToMonth(addCalendarMonths({ ...viewMonth, day: 1 }, 1))
  }, [navigateToMonth, viewMonth])

  const goToYear = useCallback(
    (year: number) => {
      if (viewMonth === null) return
      navigateToMonth({ year, month: viewMonth.month })
    },
    [navigateToMonth, viewMonth],
  )

  const retryToday = useCallback(() => {
    setIsTodayLoading(true)
    setTodayError(null)
    setTodayRetryKey((current) => current + 1)
  }, [])

  const retryRange = useCallback(() => {
    setIsRangeLoading(true)
    setRangeError(null)
    setRangeRetryKey((current) => current + 1)
  }, [])

  const selectInstance = useCallback((instance: CalendarEventInstance) => {
    detailController.current?.abort()
    const controller = new AbortController()
    const requestId = detailRequestId.current + 1
    detailRequestId.current = requestId
    detailController.current = controller
    setSelectedInstance(instance)
    setIsDetailLoading(true)
    setDetailError(null)

    void fetchCalendarInstance(instance.occurrence_id, controller.signal)
      .then((response) => {
        if (
          !controller.signal.aborted &&
          detailRequestId.current === requestId
        ) {
          setSelectedInstance(response)
        }
      })
      .catch((error: unknown) => {
        if (
          !controller.signal.aborted &&
          detailRequestId.current === requestId &&
          !isAbortError(error)
        ) {
          setDetailError(
            getCalendarErrorMessage(
              error,
              'Unable to load event details. Please try again.',
            ),
          )
        }
      })
      .finally(() => {
        if (
          !controller.signal.aborted &&
          detailRequestId.current === requestId
        ) {
          setIsDetailLoading(false)
        }
      })
  }, [])

  const closeSelectedInstance = useCallback(() => {
    detailController.current?.abort()
    detailController.current = null
    setSelectedInstance(null)
    setDetailError(null)
    setIsDetailLoading(false)
  }, [])

  const retryDetail = useCallback(() => {
    if (selectedInstance !== null) selectInstance(selectedInstance)
  }, [selectInstance, selectedInstance])

  const refreshAfterMutation = useCallback(() => {
    setIsRangeLoading(true)
    setIsTodayLoading(true)
    setRangeError(null)
    setTodayError(null)
    setRangeRetryKey((current) => current + 1)
    setTodayRetryKey((current) => current + 1)
  }, [])

  const handleFocusDate = useCallback((date: CalendarDate) => {
    setFocusedDate(date)
  }, [])

  return {
    academyToday,
    closeSelectedInstance,
    detailError,
    events,
    focusedDate,
    goToNextMonth,
    goToPreviousMonth,
    goToYear,
    handleFocusDate,
    isInitialLoading: viewMonth === null || isTodayLoading,
    isDetailLoading,
    isRangeLoading,
    isTodayLoading,
    navigateToMonth,
    rangeError,
    refreshAfterMutation,
    retryRange,
    retryDetail,
    retryToday,
    selectInstance,
    selectedInstance,
    setSelectedInstance,
    todayError,
    todayEvents,
    viewMonth,
  }
}
