// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import DateOfBirthPicker from './DateOfBirthPicker'

interface PickerHarnessProps {
  initialValue?: string
  disabled?: boolean
  error?: string
  clearable?: boolean
  onChange?: (value: string) => void
}

function PickerHarness({
  initialValue = '',
  disabled,
  error,
  clearable,
  onChange,
}: PickerHarnessProps) {
  const [value, setValue] = useState(initialValue)
  return (
    <>
      <label htmlFor="test-date-of-birth">Date of birth</label>
      <DateOfBirthPicker
        id="test-date-of-birth"
        value={value}
        disabled={disabled}
        error={error}
        errorId={error ? 'test-date-error' : undefined}
        clearable={clearable}
        onChange={(nextValue) => {
          setValue(nextValue)
          onChange?.(nextValue)
        }}
      />
      {error ? <p id="test-date-error">{error}</p> : null}
      <button type="button">Next field</button>
    </>
  )
}

function DateRangeHarness() {
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  return (
    <>
      <label htmlFor="test-start-date">Start date</label>
      <DateOfBirthPicker
        id="test-start-date"
        label="start date"
        value={startDate}
        onChange={setStartDate}
      />
      <label htmlFor="test-end-date">End date</label>
      <DateOfBirthPicker
        id="test-end-date"
        label="end date"
        value={endDate}
        onChange={setEndDate}
      />
    </>
  )
}

function openPicker() {
  fireEvent.click(screen.getByRole('button', { name: 'Date of birth' }))
}

function flushFocusRestoration() {
  act(() => vi.runOnlyPendingTimers())
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date', 'setTimeout', 'clearTimeout'] })
  vi.setSystemTime(new Date(2026, 6, 27, 12))
})

afterEach(() => {
  cleanup()
  vi.runOnlyPendingTimers()
  vi.useRealTimers()
})

describe('DateOfBirthPicker', () => {
  it('displays the placeholder and opens on the current month without selecting', () => {
    const onChange = vi.fn()
    render(<PickerHarness onChange={onChange} />)

    expect(screen.getByRole('button', { name: 'Date of birth' })).toHaveTextContent(
      'Select date of birth',
    )
    openPicker()

    expect(
      screen.getByRole('dialog', {
        name: 'Choose date of birth, July 2026',
      }),
    ).toHaveClass('w-80', 'max-w-[calc(100vw-1.5rem)]')
    expect(screen.getByRole('combobox', { name: 'Month' })).toHaveValue('7')
    expect(screen.getByRole('combobox', { name: 'Year' })).toHaveValue('2026')
    expect(onChange).not.toHaveBeenCalled()
  })

  it('formats an ISO value without a timezone-related day shift', () => {
    render(<PickerHarness initialValue="2005-08-17" />)
    expect(screen.getByRole('button', { name: 'Date of birth' })).toHaveTextContent(
      'August 17, 2005',
    )
  })

  it('opens an existing value on its month and exposes the selected date', () => {
    render(<PickerHarness initialValue="2005-08-17" />)
    openPicker()

    expect(screen.getByRole('combobox', { name: 'Month' })).toHaveValue('8')
    expect(screen.getByRole('combobox', { name: 'Year' })).toHaveValue('2005')
    const selected = screen.getByRole('gridcell', {
      name: 'Wednesday, August 17, 2005',
      selected: true,
    })
    expect(selected).toHaveClass('bg-academy', 'font-bold')
    expect(selected).toHaveFocus()
  })

  it('renders five weeks for July 2026 and keeps selected and future states distinct', () => {
    render(<PickerHarness initialValue="2026-07-27" />)
    openPicker()
    const grid = screen.getByRole('grid')
    const gridCells = within(grid).getAllByRole('gridcell')
    const weekRows = grid.querySelectorAll('[data-calendar-week]')
    const selected = screen.getByRole('gridcell', {
      name: 'Today, Monday, July 27, 2026',
      selected: true,
    })
    const adjacentFutureDate = screen.getByRole('gridcell', {
      name: 'Tuesday, July 28, 2026',
    })
    const outsideFutureDate = screen.getByRole('gridcell', {
      name: 'Saturday, August 1, 2026',
    })

    expect(gridCells).toHaveLength(35)
    expect(weekRows).toHaveLength(5)
    expect(selected).toHaveClass('bg-academy', 'font-bold')
    expect(selected).not.toBeDisabled()
    expect(adjacentFutureDate).not.toHaveAttribute('data-outside-month')
    expect(outsideFutureDate).toHaveAttribute('data-outside-month', 'true')
    for (const unavailableDate of [adjacentFutureDate, outsideFutureDate]) {
      expect(unavailableDate).toBeDisabled()
      expect(unavailableDate).toHaveAttribute('aria-disabled', 'true')
      expect(unavailableDate).toHaveClass(
        'disabled:bg-transparent',
        'disabled:text-slate-400',
      )
      expect(unavailableDate).not.toHaveClass('bg-academy')
    }
  })

  it('consistently mutes leading and trailing dates outside a five-week month', () => {
    render(<PickerHarness initialValue="2025-07-15" />)
    openPicker()

    const leadingDate = screen.getByRole('gridcell', {
      name: 'Sunday, June 29, 2025',
    })
    const trailingDate = screen.getByRole('gridcell', {
      name: 'Saturday, August 2, 2025',
    })
    const currentMonthDate = screen.getByRole('gridcell', {
      name: 'Tuesday, July 1, 2025',
    })
    const selectedDate = screen.getByRole('gridcell', {
      name: 'Tuesday, July 15, 2025',
      selected: true,
    })

    for (const outsideDate of [leadingDate, trailingDate]) {
      expect(outsideDate).toHaveAttribute('data-outside-month', 'true')
      expect(outsideDate).toHaveClass('bg-transparent', 'text-slate-500')
      expect(outsideDate).not.toBeDisabled()
      expect(outsideDate).not.toHaveClass('text-slate-900')
    }
    expect(currentMonthDate).not.toHaveAttribute('data-outside-month')
    expect(currentMonthDate).toHaveClass('text-slate-900')
    expect(currentMonthDate).not.toHaveClass('text-slate-500')
    expect(selectedDate).toHaveClass(
      'bg-academy',
      'font-bold',
      'text-slate-950',
    )
    expect(selectedDate).not.toHaveClass('text-slate-500')
  })

  it('renders six weeks where required without a seventh row or duplicate dates', () => {
    render(<PickerHarness initialValue="2025-08-31" />)
    openPicker()
    const grid = screen.getByRole('grid')
    const gridCells = within(grid).getAllByRole('gridcell')
    const weekRows = grid.querySelectorAll('[data-calendar-week]')
    const isoDates = gridCells.map((cell) =>
      cell.getAttribute('data-calendar-date'),
    )

    expect(gridCells).toHaveLength(42)
    expect(weekRows).toHaveLength(6)
    expect(
      grid.querySelector('[data-calendar-week="7"]'),
    ).not.toBeInTheDocument()
    expect(new Set(isoDates).size).toBe(42)
    expect(isoDates[0]).toBe('2025-07-27')
    expect(isoDates[41]).toBe('2025-09-06')
    expect(gridCells[0]).toHaveClass('text-slate-500')
    expect(gridCells[0]).not.toHaveClass('text-slate-900')
    expect(gridCells[41]).toHaveClass('text-slate-500')
    expect(gridCells[41]).not.toHaveClass('text-slate-900')
    expect(
      screen.getByRole('gridcell', {
        name: 'Friday, August 1, 2025',
      }),
    ).toHaveClass('text-slate-900')
    expect(
      screen.getByRole('gridcell', {
        name: 'Sunday, August 31, 2025',
        selected: true,
      }),
    ).toHaveClass('bg-academy', 'text-slate-950')
  })

  it('closes with Escape and restores focus to the trigger', () => {
    render(<PickerHarness initialValue="2005-08-17" />)
    const trigger = screen.getByRole('button', { name: 'Date of birth' })
    openPicker()

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    flushFocusRestoration()
    expect(trigger).toHaveFocus()
  })

  it('closes on outside interaction without stealing focus', () => {
    render(<PickerHarness />)
    const trigger = screen.getByRole('button', { name: 'Date of birth' })
    openPicker()

    fireEvent.pointerDown(document.body)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    flushFocusRestoration()
    expect(trigger).not.toHaveFocus()
  })

  it('closes without restoring focus when focus leaves the picker group', () => {
    render(<PickerHarness />)
    openPicker()
    const nextField = screen.getByRole('button', { name: 'Next field' })

    nextField.focus()
    fireEvent.focusIn(nextField)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(nextField).toHaveFocus()
  })

  it('does not steal focus when moving directly between date pickers', () => {
    render(<DateRangeHarness />)
    const startDate = screen.getByRole('button', { name: 'Start date' })
    const endDate = screen.getByRole('button', { name: 'End date' })
    fireEvent.click(startDate)

    fireEvent.pointerDown(endDate)
    endDate.focus()
    fireEvent.click(endDate)
    flushFocusRestoration()

    expect(startDate).toHaveAttribute('aria-expanded', 'false')
    expect(endDate).toHaveAttribute('aria-expanded', 'true')
    expect(
      screen.getByRole('dialog', { name: 'Choose end date, July 2026' }),
    ).toBeVisible()
    expect(screen.getByRole('gridcell', { name: /Today,/ })).toHaveFocus()
  })

  it('emits one ISO value and closes when a date is selected', () => {
    const onChange = vi.fn()
    render(<PickerHarness onChange={onChange} />)
    openPicker()
    fireEvent.change(screen.getByRole('combobox', { name: 'Year' }), {
      target: { value: '2005' },
    })
    fireEvent.change(screen.getByRole('combobox', { name: 'Month' }), {
      target: { value: '8' },
    })

    fireEvent.click(
      screen.getByRole('gridcell', {
        name: 'Wednesday, August 17, 2005',
      }),
    )

    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith('2005-08-17')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Date of birth' })).toHaveTextContent(
      'August 17, 2005',
    )
    flushFocusRestoration()
    expect(screen.getByRole('button', { name: 'Date of birth' })).toHaveFocus()
  })

  it('restores focus after explicitly clearing a selected date', () => {
    render(<PickerHarness initialValue="2005-08-17" clearable />)
    const trigger = screen.getByRole('button', { name: 'Date of birth' })
    openPicker()

    fireEvent.click(screen.getByRole('button', { name: 'Clear date of birth' }))
    flushFocusRestoration()

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })

  it('updates the visible month and year with direct selectors', () => {
    render(<PickerHarness />)
    openPicker()
    const month = screen.getByRole('combobox', { name: 'Month' })
    const year = screen.getByRole('combobox', { name: 'Year' })

    year.focus()
    fireEvent.change(year, { target: { value: '2005' } })
    expect(year).toHaveFocus()
    month.focus()
    fireEvent.change(month, { target: { value: '8' } })

    expect(year).toHaveValue('2005')
    expect(month).toHaveValue('8')
    expect(month).toHaveFocus()
  })

  it('supports previous and next month navigation', () => {
    render(<PickerHarness initialValue="2005-08-17" />)
    openPicker()

    fireEvent.click(screen.getByRole('button', { name: 'Previous month' }))
    expect(screen.getByRole('combobox', { name: 'Month' })).toHaveValue('7')
    fireEvent.click(screen.getByRole('button', { name: 'Next month' }))
    expect(screen.getByRole('combobox', { name: 'Month' })).toHaveValue('8')
  })

  it('prevents navigation and selection outside the runtime range', () => {
    render(<PickerHarness />)
    openPicker()

    expect(screen.getByRole('button', { name: 'Next month' })).toBeDisabled()
    expect(
      screen.getByRole('gridcell', {
        name: 'Tuesday, July 28, 2026',
      }),
    ).toBeDisabled()

    fireEvent.change(screen.getByRole('combobox', { name: 'Year' }), {
      target: { value: '1926' },
    })
    expect(screen.getByRole('combobox', { name: 'Month' })).toHaveValue('7')
    expect(screen.getByRole('button', { name: 'Previous month' })).toBeDisabled()
    expect(
      screen.getByRole('gridcell', {
        name: 'Monday, July 26, 1926',
      }),
    ).toBeDisabled()
  })

  it('prevents all interaction while disabled', () => {
    render(<PickerHarness disabled />)
    const trigger = screen.getByRole('button', { name: 'Date of birth' })
    expect(trigger).toBeDisabled()
    fireEvent.click(trigger)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('exposes the error state and description relationship', () => {
    render(<PickerHarness error="Choose a date of birth." />)
    const trigger = screen.getByRole('button', { name: 'Date of birth' })
    expect(trigger).toHaveAttribute('aria-invalid', 'true')
    expect(trigger).toHaveAccessibleDescription(
      'Select date of birth Choose a date of birth.',
    )
    expect(trigger.getAttribute('aria-describedby')).toContain(
      'test-date-error',
    )
  })

  it('moves focus with arrow keys and crosses month boundaries', () => {
    render(<PickerHarness initialValue="2005-08-31" />)
    openPicker()
    const august31 = screen.getByRole('gridcell', {
      name: 'Wednesday, August 31, 2005',
    })

    fireEvent.keyDown(august31, { key: 'ArrowRight' })

    expect(screen.getByRole('combobox', { name: 'Month' })).toHaveValue('9')
    expect(
      screen.getByRole('gridcell', {
        name: 'Thursday, September 1, 2005',
      }),
    ).toHaveFocus()
  })

  it('moves from the final cell row into the next month', () => {
    render(<PickerHarness initialValue="2025-08-31" />)
    openPicker()
    const finalRowDate = screen.getByRole('gridcell', {
      name: 'Sunday, August 31, 2025',
    })

    fireEvent.keyDown(finalRowDate, { key: 'ArrowRight' })

    expect(screen.getByRole('combobox', { name: 'Month' })).toHaveValue('9')
    expect(
      screen.getByRole('gridcell', {
        name: 'Monday, September 1, 2025',
      }),
    ).toHaveFocus()
  })

  it.each(['Enter', ' '])(
    'selects the focused date with the %s key',
    (key) => {
      const onChange = vi.fn()
      render(
        <PickerHarness initialValue="2005-08-17" onChange={onChange} />,
      )
      openPicker()
      const selectedDate = screen.getByRole('gridcell', {
        name: 'Wednesday, August 17, 2005',
      })

      fireEvent.keyDown(selectedDate, { key })

      expect(onChange).toHaveBeenCalledTimes(1)
      expect(onChange).toHaveBeenCalledWith('2005-08-17')
    },
  )

  it('allows February 29 in a leap year and omits it in a non-leap year', () => {
    render(<PickerHarness />)
    openPicker()
    const year = screen.getByRole('combobox', { name: 'Year' })
    const month = screen.getByRole('combobox', { name: 'Month' })

    fireEvent.change(year, { target: { value: '2024' } })
    fireEvent.change(month, { target: { value: '2' } })
    expect(
      screen.getByRole('gridcell', {
        name: 'Thursday, February 29, 2024',
      }),
    ).toBeEnabled()

    fireEvent.change(year, { target: { value: '2025' } })
    expect(
      screen.queryByRole('gridcell', { name: /February 29, 2025/ }),
    ).not.toBeInTheDocument()
  })
})
