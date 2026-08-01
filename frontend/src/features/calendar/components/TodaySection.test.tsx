// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import TodaySection from './TodaySection'
import type { CalendarEventInstance } from '../types/calendar'

function makeEvent(
  overrides: Partial<CalendarEventInstance> = {},
): CalendarEventInstance {
  return {
    occurrence_id: 'event-1',
    event_id: 'event-1',
    series_id: null,
    original_date: '2026-08-01',
    event_date: '2026-08-01',
    event_type: 'practice',
    name: 'Afternoon practice',
    is_all_day: false,
    start_time: '15:00:00',
    end_time: '16:00:00',
    scope_kind: 'age_group',
    age_groups: ['U13'],
    is_recurring: false,
    recurrence_summary: null,
    event_version_number: 1,
    exception_id: null,
    exception_version_number: null,
    ...overrides,
  }
}

afterEach(cleanup)

describe('TodaySection', () => {
  it('shows the exact empty-state copy', () => {
    render(
      <TodaySection
        academyToday="2026-08-01"
        events={[]}
        isLoading={false}
        errorMessage={null}
        onRetry={vi.fn()}
        onSelectEvent={vi.fn()}
      />,
    )

    expect(screen.getByText('No events scheduled for today.')).toBeInTheDocument()
  })

  it('orders all-day and timed events, indicates recurrence, and selects an event', () => {
    const onSelectEvent = vi.fn()
    render(
      <TodaySection
        academyToday="2026-08-01"
        events={[
          makeEvent({ occurrence_id: 'late', name: 'Late game', event_type: 'game', start_time: '19:00:00' }),
          makeEvent({ occurrence_id: 'all-day', name: 'Academy meeting', event_type: 'miscellaneous', is_all_day: true, start_time: null, end_time: null }),
          makeEvent({ occurrence_id: 'recurring', name: 'Morning series', is_recurring: true, series_id: 'series-1', start_time: '08:00:00', recurrence_summary: 'Every week on Saturday' }),
        ]}
        isLoading={false}
        errorMessage={null}
        onRetry={vi.fn()}
        onSelectEvent={onSelectEvent}
      />,
    )

    const entries = screen.getAllByRole('button', { name: /event:/i })
    expect(entries[0]).toHaveAccessibleName(/Academy meeting/)
    expect(entries[1]).toHaveAccessibleName(/Morning series/)
    expect(screen.getByText('Every week on Saturday')).toBeInTheDocument()
    fireEvent.click(entries[1])
    expect(onSelectEvent).toHaveBeenCalledWith(expect.objectContaining({ occurrence_id: 'recurring' }))
  })

  it('keeps Today failures retryable and loading inline', () => {
    const onRetry = vi.fn()
    const { rerender } = render(
      <TodaySection
        academyToday="2026-08-01"
        events={[]}
        isLoading={true}
        errorMessage={null}
        onRetry={onRetry}
        onSelectEvent={vi.fn()}
      />,
    )
    expect(screen.getByRole('status')).toHaveTextContent('Loading Today')

    rerender(
      <TodaySection
        academyToday="2026-08-01"
        events={[]}
        isLoading={false}
        errorMessage="Unable to load Today. Please try again."
        onRetry={onRetry}
        onSelectEvent={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Retry Today' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })
})
