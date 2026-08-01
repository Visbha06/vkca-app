import { useState } from 'react'
import { useAuth } from '@features/auth'
import useSuccessToast from '@shared/hooks/useSuccessToast'
import type { CalendarDate } from '@shared/utils/calendarDate'
import type { CalendarEventInstance } from '../types/calendar'
import useCalendarData from '../hooks/useCalendarData'
import CalendarErrorState from '../components/CalendarErrorState'
import CalendarHeader from '../components/CalendarHeader'
import CalendarLoadingState from '../components/CalendarLoadingState'
import CalendarMonthGrid from '../components/CalendarMonthGrid'
import CalendarPageOverlays from '../components/CalendarPageOverlays'
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
  const [formEvent, setFormEvent] = useState<CalendarEventInstance | 'create' | null>(null)
  const [deleteEvent, setDeleteEvent] = useState<CalendarEventInstance | null>(null)
  const { dismissSuccessToast, showSuccessToast, successToast } = useSuccessToast()
  const canManage = user?.role === 'head coach' || user?.role === 'assistant coach'

  function handlePreviousMonth() {
    calendar.goToPreviousMonth()
  }

  function handleNextMonth() {
    calendar.goToNextMonth()
  }

  function handleYearChange(year: number) {
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

  function handleEditEvent(event: CalendarEventInstance) {
    handleCloseDetails()
    setFormEvent(event)
  }

  function handleDeleteEvent(event: CalendarEventInstance) {
    handleCloseDetails()
    setDeleteEvent(event)
  }

  function handleMutationComplete(message: string) {
    setFormEvent(null)
    setDeleteEvent(null)
    setOpenedEvent(null)
    calendar.closeSelectedInstance()
    calendar.refreshAfterMutation()
    showSuccessToast(message)
  }

  function handleEventReloaded(event: CalendarEventInstance) {
    setOpenedEvent(event)
    calendar.setSelectedInstance(event)
  }

  const initialLoading = calendar.viewMonth === null || calendar.academyToday === null

  return (
    <section className="mx-auto w-full max-w-7xl" aria-labelledby="calendar-page-title">
      <div className="mb-6">
        <h1 id="calendar-page-title" className="text-3xl font-bold tracking-tight text-slate-900" tabIndex={-1}>
          Calendar
        </h1>
        <p className="mt-2 max-w-none text-slate-600 md:whitespace-nowrap">
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
              onCreateEvent={canManage ? () => setFormEvent('create') : undefined}
            />
            <div className="mt-4 min-w-0">
              {calendar.rangeError !== null ? (
                <div className="mb-4">
                  <CalendarErrorState message={calendar.rangeError} onRetry={calendar.retryRange} />
                </div>
              ) : null}
              {calendar.rangeError !== null && calendar.events.length === 0 ? null : (
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

      <CalendarPageOverlays
        calendar={calendar}
        canManage={canManage}
        openedEvent={openedEvent}
        formEvent={formEvent}
        deleteEvent={deleteEvent}
        overflow={overflow}
        successToast={successToast}
        onCloseDetails={handleCloseDetails}
        onEdit={handleEditEvent}
        onDelete={handleDeleteEvent}
        onCloseForm={() => setFormEvent(null)}
        onCloseDelete={() => setDeleteEvent(null)}
        onCloseOverflow={() => setOverflow(null)}
        onSelectEvent={handleSelectEvent}
        onMutationComplete={handleMutationComplete}
        onEventReloaded={handleEventReloaded}
        onDismissToast={dismissSuccessToast}
      />
      <p className="sr-only" aria-live="polite">
        {user?.role === 'player' ? 'Calendar is read-only for Players.' : 'Calendar events are displayed in academy time.'}
      </p>
    </section>
  )
}
