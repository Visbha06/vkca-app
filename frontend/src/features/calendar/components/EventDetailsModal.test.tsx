// @vitest-environment jsdom

import { useState } from 'react'
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { CalendarEventInstance } from '../types/calendar'
import EventDetailsModal from './EventDetailsModal'

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
  vi.clearAllMocks()
})

describe('EventDetailsModal recovery', () => {
  it('keeps the event context visible and retries a failed detail request', () => {
    const onRetry = vi.fn()
    render(
      <EventDetailsModal
        event={eventFixture()}
        isLoading={false}
        errorMessage="Unable to load event details. Please try again."
        onRetry={onRetry}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Wednesday practice' })).toBeVisible()
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Unable to load event details. Please try again.',
    )
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('announces loading and withholds mutation controls until details are current', () => {
    render(
      <EventDetailsModal
        event={eventFixture()}
        isLoading
        errorMessage={null}
        onRetry={vi.fn()}
        onClose={vi.fn()}
        canManage
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />,
    )

    expect(screen.getByRole('status')).toHaveTextContent('Loading event details')
    expect(screen.queryByRole('button', { name: 'Edit Event' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Delete Event' })).not.toBeInTheDocument()
  })

  it('closes with Escape and restores focus to the event trigger', () => {
    function Harness() {
      const [open, setOpen] = useState(false)
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>
            Open Wednesday practice
          </button>
          {open ? (
            <EventDetailsModal
              event={eventFixture()}
              isLoading={false}
              errorMessage={null}
              onRetry={vi.fn()}
              onClose={() => setOpen(false)}
            />
          ) : null}
        </>
      )
    }

    render(<Harness />)
    const trigger = screen.getByRole('button', {
      name: 'Open Wednesday practice',
    })
    trigger.focus()
    fireEvent.click(trigger)
    expect(screen.getByRole('button', { name: 'Close event details' })).toHaveFocus()

    fireEvent.keyDown(document, { key: 'Escape' })

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })
})
