// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CalendarMonthGrid from './CalendarMonthGrid'
import type { CalendarEventInstance } from '../types/calendar'

function makeEvent(
  overrides: Partial<CalendarEventInstance> = {},
): CalendarEventInstance {
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
    ...overrides,
  }
}

describe('CalendarMonthGrid', () => {
  afterEach(cleanup)

  it('renders a complete semantic grid with current and adjacent date treatment', () => {
    render(
      <CalendarMonthGrid
        viewMonth={{ year: 2026, month: 8 }}
        academyToday="2026-08-05"
        events={[makeEvent()]}
        focusedDate={{ year: 2026, month: 8, day: 5 }}
        onFocusDate={vi.fn()}
        onSelectEvent={vi.fn()}
        onSelectMore={vi.fn()}
      />,
    )

    expect(screen.getByRole('grid', { name: 'August 2026 calendar' })).toBeInTheDocument()
    expect(screen.getAllByRole('columnheader')).toHaveLength(7)
    expect(screen.getByRole('button', { name: /Today, Wednesday, August 5, 2026/ })).toHaveAttribute('aria-current', 'date')
    for (const day of [26, 27, 28, 29, 30, 31]) {
      expect(
        screen.getByRole('button', {
          name: new RegExp(`July ${day}, 2026`),
        }),
      ).toHaveClass('text-slate-500')
    }
    for (const day of [1, 2, 3, 4, 5]) {
      expect(
        screen.getByRole('button', {
          name: new RegExp(`September ${day}, 2026`),
        }),
      ).toHaveClass('text-slate-500')
    }
    for (const day of [1, 4, 31]) {
      const augustDate = screen.getByRole('button', {
        name: new RegExp(`August ${day}, 2026`),
      })
      expect(augustDate).not.toHaveAttribute('data-outside-month')
      expect(augustDate).not.toHaveClass('text-slate-500')
    }
    expect(screen.getByRole('button', { name: /Wednesday practice/ })).toBeInTheDocument()
  })

  it('orders entries, limits visible entries to three, and exposes accessible overflow', () => {
    const events = [
      makeEvent({ occurrence_id: 'event-1', name: 'Wednesday practice', start_time: '17:00:00' }),
      makeEvent({ occurrence_id: 'all-day', name: 'Academy meeting', is_all_day: true, start_time: null, end_time: null, event_type: 'miscellaneous' }),
      makeEvent({ occurrence_id: 'timed-early', name: 'Early practice', start_time: '09:00:00' }),
      makeEvent({ occurrence_id: 'fourth', name: 'Fourth event' }),
    ]

    render(
      <CalendarMonthGrid
        viewMonth={{ year: 2026, month: 8 }}
        academyToday="2026-08-01"
        events={events}
        focusedDate={{ year: 2026, month: 8, day: 1 }}
        onFocusDate={vi.fn()}
        onSelectEvent={vi.fn()}
        onSelectMore={vi.fn()}
      />,
    )

    const entryNames = screen.getAllByRole('button', { name: /event:/i })
      .map((button) => button.textContent)
    expect(entryNames.slice(0, 3)).toEqual([
      expect.stringContaining('Academy meeting'),
      expect.stringContaining('Early practice'),
      expect.stringContaining('Wednesday practice'),
    ])
    expect(screen.getByRole('button', { name: '1 more event on Wednesday, August 5, 2026' })).toBeInTheDocument()
    expect(screen.queryByText('Fourth event')).not.toBeInTheDocument()
  })
})
