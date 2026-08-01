// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
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
    const today = screen.getByRole('gridcell', {
      name: /Wednesday, August 5, 2026, current academy date/,
    })
    const todayNumber = today.querySelector('[data-calendar-date-number]')
    expect(today).toHaveAttribute('aria-current', 'date')
    expect(today).toHaveAttribute('data-date-state', 'today')
    expect(today).not.toHaveAttribute('aria-selected')
    expect(todayNumber).toHaveClass(
      'border-academy',
      'bg-academy/10',
      'text-slate-950',
      'group-focus:ring-2',
      'group-focus:ring-slate-900',
      'group-focus:ring-inset',
    )
    for (const day of [26, 27, 28, 29, 30, 31]) {
      const outsideDate = screen.getByRole('gridcell', {
          name: new RegExp(`July ${day}, 2026`),
        })
      expect(outsideDate).toHaveAttribute('data-outside-month', 'true')
      expect(outsideDate).toHaveAttribute('data-date-state', 'outside-month')
      expect(outsideDate).not.toHaveAttribute('aria-current')
      expect(outsideDate).not.toHaveAttribute('aria-selected')
      expect(outsideDate.querySelector('[data-calendar-date-number]')).toHaveClass(
        'text-slate-500',
        'hover:bg-academy/10',
        'hover:text-slate-700',
        'group-focus:ring-slate-900',
      )
    }
    for (const day of [1, 2, 3, 4, 5]) {
      const outsideDate = screen.getByRole('gridcell', {
          name: new RegExp(`September ${day}, 2026`),
        })
      expect(outsideDate).toHaveAttribute('data-outside-month', 'true')
      expect(outsideDate).toHaveAttribute('data-date-state', 'outside-month')
      expect(outsideDate.querySelector('[data-calendar-date-number]')).toHaveClass(
        'text-slate-500',
        'hover:text-slate-700',
        'group-focus:ring-slate-900',
      )
    }
    for (const day of [1, 4, 31]) {
      const augustDate = screen.getByRole('gridcell', {
        name: new RegExp(`August ${day}, 2026`),
      })
      expect(augustDate).not.toHaveAttribute('data-outside-month')
      expect(augustDate).toHaveAttribute('data-date-state', 'normal')
      expect(augustDate).not.toHaveAttribute('aria-current')
      expect(augustDate).not.toHaveAttribute('aria-selected')
      expect(augustDate.querySelector('[data-calendar-date-number]')).toHaveClass(
        'border-transparent',
        'text-slate-800',
        'hover:bg-academy/10',
        'group-focus:ring-slate-900',
      )
    }
    expect(document.querySelectorAll('[aria-current="date"]')).toHaveLength(1)
    expect(document.querySelector('[aria-selected]')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Wednesday practice/ })).toBeInTheDocument()
  })

  it('moves DOM focus through visible dates with the supported grid keys', () => {
    function KeyboardHarness() {
      const [focusedDate, setFocusedDate] = useState({ year: 2026, month: 8, day: 5 })
      return (
        <CalendarMonthGrid
          viewMonth={{ year: 2026, month: 8 }}
          academyToday="2026-08-05"
          events={[makeEvent()]}
          focusedDate={focusedDate}
          onFocusDate={setFocusedDate}
          onSelectEvent={vi.fn()}
          onSelectMore={vi.fn()}
        />
      )
    }

    render(<KeyboardHarness />)

    const focusDate = (name: RegExp) => screen.getByRole('gridcell', { name })
    const august5 = focusDate(/August 5, 2026/)
    august5.focus()

    for (const [key, nextDate] of [
      ['ArrowRight', /August 6, 2026/],
      ['ArrowDown', /August 13, 2026/],
      ['Home', /August 9, 2026/],
      ['End', /August 15, 2026/],
      ['ArrowLeft', /August 14, 2026/],
      ['ArrowUp', /August 7, 2026/],
    ] as const) {
      fireEvent.keyDown(document.activeElement!, { key })
      const activeDate = focusDate(nextDate)
      expect(activeDate).toHaveFocus()
      expect(activeDate).toHaveAttribute('tabindex', '0')
    }

    const firstVisibleDate = focusDate(/July 26, 2026/)
    firstVisibleDate.focus()
    fireEvent.keyDown(firstVisibleDate, { key: 'ArrowLeft' })
    expect(firstVisibleDate).toHaveFocus()

    const lastVisibleDate = focusDate(/September 5, 2026/)
    lastVisibleDate.focus()
    fireEvent.keyDown(lastVisibleDate, { key: 'ArrowRight' })
    expect(lastVisibleDate).toHaveFocus()

    const eventButton = screen.getByRole('button', { name: /Wednesday practice/ })
    eventButton.focus()
    fireEvent.keyDown(eventButton, { key: 'ArrowRight' })
    expect(eventButton).toHaveFocus()
  })

  it('uses non-actionable gridcells for dates and leaves Enter and Space inert', () => {
    const onFocusDate = vi.fn()
    const onSelectEvent = vi.fn()
    const onSelectMore = vi.fn()
    render(
      <CalendarMonthGrid
        viewMonth={{ year: 2026, month: 8 }}
        academyToday="2026-08-05"
        events={[]}
        focusedDate={{ year: 2026, month: 8, day: 5 }}
        onFocusDate={onFocusDate}
        onSelectEvent={onSelectEvent}
        onSelectMore={onSelectMore}
      />,
    )

    const dateCell = screen.getByRole('gridcell', { name: /August 5, 2026/ })
    expect(screen.queryByRole('button', { name: /August 5, 2026/ })).not.toBeInTheDocument()
    dateCell.focus()
    onFocusDate.mockClear()

    fireEvent.keyDown(dateCell, { key: 'Enter' })
    fireEvent.keyDown(dateCell, { key: ' ' })

    expect(dateCell).toHaveFocus()
    expect(onFocusDate).not.toHaveBeenCalled()
    expect(onSelectEvent).not.toHaveBeenCalled()
    expect(onSelectMore).not.toHaveBeenCalled()
  })

  it('uses a full-width compact date target to open the existing day-events view', () => {
    const onSelectMore = vi.fn()
    const events = [
      makeEvent({ occurrence_id: 'timed', name: 'Evening practice' }),
      makeEvent({
        occurrence_id: 'all-day',
        name: 'Academy meeting',
        is_all_day: true,
        start_time: null,
        end_time: null,
      }),
    ]

    render(
      <CalendarMonthGrid
        viewMonth={{ year: 2026, month: 8 }}
        academyToday="2026-08-05"
        events={events}
        focusedDate={{ year: 2026, month: 8, day: 5 }}
        onFocusDate={vi.fn()}
        onSelectEvent={vi.fn()}
        onSelectMore={onSelectMore}
      />,
    )

    const compactTarget = screen.getByRole('button', {
      name: 'View 2 events on Wednesday, August 5, 2026',
    })
    expect(compactTarget).toHaveClass('min-h-11', 'w-full', 'min-w-0', 'sm:hidden')
    expect(compactTarget).toHaveTextContent('5')
    expect(compactTarget).toHaveTextContent('2')
    expect(document.querySelector('[data-calendar-day-details="2026-08-05"]')).toHaveClass(
      'hidden',
      'sm:block',
    )

    fireEvent.click(compactTarget)

    expect(onSelectMore).toHaveBeenCalledWith(
      { year: 2026, month: 8, day: 5 },
      [
        expect.objectContaining({ occurrence_id: 'all-day' }),
        expect.objectContaining({ occurrence_id: 'timed' }),
      ],
    )
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
    const overflowButton = screen.getByRole('button', {
      name: '1 more event on Wednesday, August 5, 2026',
    })
    expect(overflowButton).toHaveClass(
      'text-slate-800',
      'hover:bg-academy/10',
      'focus:ring-academy',
    )
    expect(overflowButton).not.toHaveClass('text-academy')
    expect(screen.queryByText('Fourth event')).not.toBeInTheDocument()
  })
})
