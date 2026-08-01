import { useEffect, useRef, useState } from 'react'
import { useAuth } from '@features/auth'
import {
  calendarDateToIso,
  type CalendarDate,
} from '@shared/utils/calendarDate'
import type { CalendarEventInstance } from '../types/calendar'
import useCalendarData from '../hooks/useCalendarData'
import CalendarErrorState from '../components/CalendarErrorState'
import CalendarHeader from '../components/CalendarHeader'
import CalendarLoadingState from '../components/CalendarLoadingState'
import CalendarMonthGrid from '../components/CalendarMonthGrid'
import DayEventsModal from '../components/DayEventsModal'
import EventDetailsModal from '../components/EventDetailsModal'
import TodaySection from '../components/TodaySection'

interface OverflowState {
  date: CalendarDate
  events: CalendarEventInstance[]
}

export default function CalendarPage() {
  const { user } = useAuth()
  const calendar = useCalendarData()
  const [overflow, setOverflow] = useState<OverflowState | null>(null)
  const [openedEvent, setOpenedEvent] = useState<CalendarEventInstance | null>(null)
  const focusAfterNavigation = useRef(false)

  useEffect(() => {
    if (
      !focusAfterNavigation.current ||
      calendar.isRangeLoading ||
      calendar.focusedDate === null
    ) {
      return
    }
    focusAfterNavigation.current = false
    const target = document.querySelector<HTMLButtonElement>(
      `[data-calendar-date-button="${calendarDateToIso(calendar.focusedDate)}"]`,
    )
    target?.focus()
  }, [calendar.focusedDate, calendar.isRangeLoading])

  function handlePreviousMonth() {
    focusAfterNavigation.current = true
    calendar.goToPreviousMonth()
  }

  function handleNextMonth() {
    focusAfterNavigation.current = true
    calendar.goToNextMonth()
  }

  function handleYearChange(year: number) {
    focusAfterNavigation.current = true
    calendar.goToYear(year)
  }

  function handleSelectEvent(event: CalendarEventInstance) {
    setOverflow(null)
    setOpenedEvent(event)
    calendar.selectInstance(event)
  }

  function handleCloseDetails() {
    setOpenedEvent(null)
    calendar.closeSelectedInstance()
  }

  const initialLoading = calendar.viewMonth === null || calendar.academyToday === null

  return (
    <section className="mx-auto w-full max-w-7xl" aria-labelledby="calendar-page-title">
      <div className="mb-6">
        <h1 id="calendar-page-title" className="text-3xl font-bold tracking-tight text-slate-900" tabIndex={-1}>
          Calendar
        </h1>
        <p className="mt-2 max-w-prose text-slate-600">
          Review academy events in Pacific time and keep today’s schedule close at hand.
        </p>
      </div>

      {initialLoading ? (
        <>
          {calendar.todayError !== null ? (
            <CalendarErrorState message={calendar.todayError} onRetry={calendar.retryToday} />
          ) : <CalendarLoadingState />}
          <TodaySection
            academyToday={calendar.academyToday}
            events={calendar.todayEvents}
            isLoading={calendar.isTodayLoading}
            errorMessage={calendar.todayError}
            onRetry={calendar.retryToday}
            onSelectEvent={handleSelectEvent}
          />
        </>
      ) : (
        <>
          <section aria-labelledby="calendar-month-heading" className="min-w-0">
            <CalendarHeader
              viewMonth={calendar.viewMonth!}
              academyToday={calendar.academyToday!}
              isLoading={calendar.isRangeLoading}
              onPreviousMonth={handlePreviousMonth}
              onNextMonth={handleNextMonth}
              onYearChange={handleYearChange}
            />
            <div className="mt-4 min-w-0">
              {calendar.rangeError !== null && calendar.events.length === 0 ? (
                <CalendarErrorState message={calendar.rangeError} onRetry={calendar.retryRange} />
              ) : (
                <CalendarMonthGrid
                  viewMonth={calendar.viewMonth!}
                  academyToday={calendar.academyToday}
                  events={calendar.events}
                  focusedDate={calendar.focusedDate!}
                  isLoading={calendar.isRangeLoading}
                  onFocusDate={calendar.handleFocusDate}
                  onSelectEvent={handleSelectEvent}
                  onSelectMore={(date, events) => setOverflow({ date, events })}
                />
              )}
            </div>
          </section>
          <TodaySection
            academyToday={calendar.academyToday}
            events={calendar.todayEvents}
            isLoading={calendar.isTodayLoading}
            errorMessage={calendar.todayError}
            onRetry={calendar.retryToday}
            onSelectEvent={handleSelectEvent}
          />
        </>
      )}

      {calendar.selectedInstance !== null || openedEvent !== null ? (
        <EventDetailsModal
          event={calendar.selectedInstance ?? openedEvent!}
          isLoading={calendar.isDetailLoading}
          errorMessage={calendar.detailError}
          onRetry={calendar.retryDetail}
          onClose={handleCloseDetails}
        />
      ) : null}
      {overflow !== null ? (
        <DayEventsModal
          date={overflow.date}
          events={overflow.events}
          onSelectEvent={handleSelectEvent}
          onClose={() => setOverflow(null)}
        />
      ) : null}
      <p className="sr-only" aria-live="polite">
        {user?.role === 'player' ? 'Calendar is read-only for Players.' : 'Calendar events are displayed in academy time.'}
      </p>
    </section>
  )
}
