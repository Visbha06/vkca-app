// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CalendarHeader from './CalendarHeader'

describe('CalendarHeader', () => {
  afterEach(cleanup)

  it('moves one month and exposes dynamic academy year options', () => {
    const onNextMonth = vi.fn()
    const onPreviousMonth = vi.fn()
    const onYearChange = vi.fn()

    render(
      <CalendarHeader
        viewMonth={{ year: 2026, month: 12 }}
        academyToday="2026-08-01"
        isLoading={false}
        onPreviousMonth={onPreviousMonth}
        onNextMonth={onNextMonth}
        onYearChange={onYearChange}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Next month' }))
    fireEvent.click(screen.getByRole('button', { name: 'Previous month' }))
    fireEvent.change(screen.getByRole('combobox', { name: 'Calendar year' }), {
      target: { value: '2031' },
    })

    expect(onNextMonth).toHaveBeenCalledOnce()
    expect(onPreviousMonth).toHaveBeenCalledOnce()
    expect(onYearChange).toHaveBeenCalledWith(2031)
    expect(screen.getByRole('heading', { name: 'December 2026' })).not.toHaveClass('mt-1')
    expect(screen.queryByText('Academy calendar')).not.toBeInTheDocument()
    expect(screen.getByRole('option', { name: '2031' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: '2032' })).not.toBeInTheDocument()
  })

  it('keeps historical arrow navigation available without adding pre-2026 selector years', () => {
    render(
      <CalendarHeader
        viewMonth={{ year: 2025, month: 12 }}
        academyToday="2026-08-01"
        isLoading={false}
        onPreviousMonth={vi.fn()}
        onNextMonth={vi.fn()}
        onYearChange={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: 'Previous month' })).not.toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next month' })).not.toBeDisabled()
    expect(screen.getByText('Viewing historical year 2025')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('December 2025 ready')
    expect(screen.queryByRole('option', { name: '2025' })).not.toBeInTheDocument()
  })

  it('defines an explicit responsive control layout with 44px interaction targets', () => {
    render(
      <CalendarHeader
        viewMonth={{ year: 2026, month: 8 }}
        academyToday="2026-08-01"
        isLoading={false}
        onPreviousMonth={vi.fn()}
        onNextMonth={vi.fn()}
        onYearChange={vi.fn()}
        onCreateEvent={vi.fn()}
      />,
    )

    const heading = screen.getByRole('heading', { name: 'August 2026' })
    const header = heading.closest('header')
    const controls = screen.getByTestId('calendar-header-controls')
    const createEvent = screen.getByRole('button', { name: 'Create Event' })
    const year = screen.getByRole('combobox', { name: 'Calendar year' })
    const monthNavigation = screen.getByRole('group', { name: 'Month navigation' })
    const previousMonth = screen.getByRole('button', { name: 'Previous month' })
    const nextMonth = screen.getByRole('button', { name: 'Next month' })

    expect(header).toHaveClass('grid', 'sm:flex')
    expect(controls).toHaveClass('grid', 'sm:flex')
    expect(createEvent).toHaveClass('min-h-11', 'w-full', 'sm:w-auto')
    expect(year).toHaveClass('min-h-11')
    expect(monthNavigation).toHaveClass('flex-nowrap')
    expect(previousMonth).toHaveClass('min-h-11', 'min-w-11')
    expect(nextMonth).toHaveClass('min-h-11', 'min-w-11')
  })
})
