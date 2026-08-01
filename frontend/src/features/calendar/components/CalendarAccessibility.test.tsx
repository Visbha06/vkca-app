// @vitest-environment jsdom

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { useState } from 'react'
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  deleteStandaloneCalendarEvent,
} from '../api/calendarApi'
import type { CalendarEventInstance } from '../types/calendar'
import CalendarDeleteDialog from './CalendarDeleteDialog'
import EventDetailsModal from './EventDetailsModal'
import EventFormModal from './EventFormModal'

vi.mock('../api/calendarApi', () => ({
  createCalendarEvent: vi.fn(),
  deleteCalendarOccurrence: vi.fn(),
  deleteCalendarSeries: vi.fn(),
  deleteStandaloneCalendarEvent: vi.fn(),
  fetchCalendarInstance: vi.fn(),
  updateCalendarOccurrence: vi.fn(),
  updateCalendarSeries: vi.fn(),
  updateStandaloneCalendarEvent: vi.fn(),
}))

const mockedDeleteStandalone = vi.mocked(deleteStandaloneCalendarEvent)

function eventFixture(): CalendarEventInstance {
  return {
    occurrence_id: 'event-1',
    event_id: 'event-1',
    series_id: null,
    original_date: '2026-08-05',
    event_date: '2026-08-05',
    event_type: 'practice',
    name: 'Wednesday practice',
    is_all_day: false,
    start_time: '17:00:00',
    end_time: '18:30:00',
    scope_kind: 'age_group',
    age_groups: ['U13'],
    is_recurring: false,
    recurrence_summary: null,
    event_version_number: 1,
    exception_id: null,
    exception_version_number: null,
  }
}

afterEach(() => {
  cleanup()
  vi.resetAllMocks()
})

describe('Calendar accessibility and responsive resilience', () => {
  it('traps focus, closes safely with Escape, and restores the trigger', () => {
    function Harness() {
      const [open, setOpen] = useState(false)
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>
            Open event details
          </button>
          {open ? (
            <EventDetailsModal
              event={eventFixture()}
              isLoading={false}
              errorMessage={null}
              onRetry={vi.fn()}
              onClose={() => setOpen(false)}
              canManage
              onEdit={vi.fn()}
              onDelete={vi.fn()}
            />
          ) : null}
        </>
      )
    }

    render(<Harness />)
    const trigger = screen.getByRole('button', { name: 'Open event details' })
    trigger.focus()
    fireEvent.click(trigger)

    const close = screen.getByRole('button', { name: 'Close event details' })
    const deleteButton = screen.getByRole('button', { name: 'Delete Event' })
    expect(close).toHaveFocus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(deleteButton).toHaveFocus()
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
    expect(close).toHaveFocus()

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })

  it('associates form errors with their controls and exposes a visible focus target', async () => {
    render(
      <EventFormModal
        academyToday="2026-08-01"
        onClose={vi.fn()}
        onSaved={vi.fn()}
        onEventReloaded={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Create event' }))

    const nameInput = screen.getByRole('textbox', { name: /Event name/ })
    const errorId = nameInput.getAttribute('aria-describedby')
    expect(nameInput).toHaveAttribute('aria-invalid', 'true')
    expect(errorId).toBeTruthy()
    expect(document.getElementById(errorId!)).toHaveTextContent(
      'Enter an event name.',
    )
    await waitFor(() => expect(nameInput).toHaveFocus())
  })

  it('blocks Escape, announces progress, and prevents repeat delete while unsafe', async () => {
    mockedDeleteStandalone.mockImplementation(() => new Promise(() => undefined))
    const onClose = vi.fn()
    render(
      <CalendarDeleteDialog
        event={eventFixture()}
        onClose={onClose}
        onDeleted={vi.fn()}
        onEventReloaded={vi.fn()}
      />,
    )

    const deleteButton = screen.getByRole('button', { name: 'Delete event' })
    expect(deleteButton).toHaveClass('min-h-11')
    fireEvent.click(deleteButton)
    fireEvent.click(deleteButton)

    expect(mockedDeleteStandalone).toHaveBeenCalledOnce()
    expect(screen.getByRole('status')).toHaveTextContent('Deleting calendar event')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).not.toHaveBeenCalled()
  })

  it('keeps modal scrolling, reduced motion, forced colors, and touch targets explicit', () => {
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 320,
    })
    render(
      <EventDetailsModal
        event={eventFixture()}
        isLoading={false}
        errorMessage={null}
        onRetry={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    const dialog = screen.getByRole('dialog')
    const close = screen.getByRole('button', { name: 'Close event details' })
    expect(dialog).toHaveClass('modal-dialog')
    expect(close).toHaveClass('size-11')

    const styles = readFileSync(
      resolve(process.cwd(), 'src/styles/index.css'),
      'utf8',
    )
    expect(styles).toContain('max-height: calc(100dvh')
    expect(styles).toContain('overflow-y: auto')
    expect(styles).toContain('@media (prefers-reduced-motion: reduce)')
    expect(styles).toContain('transition-duration: 0ms')
    expect(styles).toContain('@media (forced-colors: active)')
    expect(styles).toContain('outline: calc(var(--spacing) / 2) solid CanvasText')
  })
})
