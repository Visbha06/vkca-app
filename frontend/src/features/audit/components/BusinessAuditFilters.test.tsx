// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { BusinessAuditFilters as Filters } from '../types/businessAudit'
import BusinessAuditFilters from './BusinessAuditFilters'

function FiltersHarness({ initialFilters = {} }: { initialFilters?: Filters }) {
  const [filters, setFilters] = useState(initialFilters)

  return (
    <>
      <BusinessAuditFilters
        actors={[]}
        actorErrorMessage={null}
        actorLoading={false}
        filters={filters}
        hasFilters={Object.values(filters).some(
          (value) => value !== undefined && value !== '',
        )}
        onChange={setFilters}
        onClear={() => setFilters({})}
        onRetryActors={vi.fn()}
      />
      <output data-testid="filter-state">{JSON.stringify(filters)}</output>
    </>
  )
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date', 'setTimeout', 'clearTimeout'] })
  vi.setSystemTime(new Date(2026, 7, 8, 12))
})

afterEach(() => {
  cleanup()
  vi.runOnlyPendingTimers()
  vi.useRealTimers()
})

describe('BusinessAuditFilters date pickers', () => {
  it('disables the top-level Clear filters action until a filter is active', () => {
    const { container } = render(<FiltersHarness />)

    expect(screen.getByRole('button', { name: 'Clear filters' })).toBeDisabled()
    expect(container.querySelector('[data-audit-date-range]')).toHaveClass(
      'flex-col',
      'sm:flex-row',
    )
    for (const label of ['Start date', 'End date']) {
      expect(screen.getByRole('button', { name: label })).toHaveClass(
        'text-sm',
        'font-normal',
      )
      expect(screen.getByRole('button', { name: label })).not.toHaveClass(
        'text-base',
      )
    }

    fireEvent.change(screen.getByLabelText('Category'), {
      target: { value: 'player' },
    })
    expect(screen.getByRole('button', { name: 'Clear filters' })).toBeEnabled()
  })

  it('opens, selects, and clears a Start date with the shared calendar', () => {
    render(<FiltersHarness />)
    const startDate = screen.getByRole('button', { name: 'Start date' })

    expect(startDate).toHaveTextContent('Select start date')
    fireEvent.click(startDate)
    expect(
      screen.getByRole('dialog', {
        name: 'Choose start date, August 2026',
      }),
    ).toBeVisible()

    fireEvent.click(
      screen.getByRole('gridcell', {
        name: 'Saturday, August 1, 2026',
      }),
    )
    expect(startDate).toHaveTextContent('August 1, 2026')
    expect(screen.getByTestId('filter-state')).toHaveTextContent(
      '"startDate":"2026-08-01"',
    )

    fireEvent.click(startDate)
    fireEvent.click(screen.getByRole('button', { name: 'Clear start date' }))
    expect(startDate).toHaveTextContent('Select start date')
    expect(screen.getByTestId('filter-state')).toHaveTextContent('{}')
  })

  it('opens and selects an End date while disabling dates before Start', () => {
    render(<FiltersHarness initialFilters={{ startDate: '2026-08-05' }} />)

    fireEvent.click(screen.getByRole('button', { name: 'End date' }))
    expect(
      screen.getByRole('dialog', {
        name: 'Choose end date, August 2026',
      }),
    ).toBeVisible()
    expect(
      screen.getByRole('gridcell', {
        name: 'Tuesday, August 4, 2026',
      }),
    ).toBeDisabled()

    fireEvent.click(
      screen.getByRole('gridcell', {
        name: 'Thursday, August 6, 2026',
      }),
    )
    expect(screen.getByRole('button', { name: 'End date' })).toHaveTextContent(
      'August 6, 2026',
    )
    expect(screen.getByTestId('filter-state')).toHaveTextContent(
      '"endDate":"2026-08-06"',
    )
  })

  it('restores controlled ISO dates and clears both with Clear filters', () => {
    const { container } = render(
      <FiltersHarness
        initialFilters={{
          startDate: '2026-08-01',
          endDate: '2026-08-07',
        }}
      />,
    )

    expect(screen.getByRole('button', { name: 'Start date' })).toHaveTextContent(
      'August 1, 2026',
    )
    expect(screen.getByRole('button', { name: 'End date' })).toHaveTextContent(
      'August 7, 2026',
    )
    expect(container.querySelector('input[type="date"]')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(screen.getByRole('button', { name: 'Start date' })).toHaveTextContent(
      'Select start date',
    )
    expect(screen.getByRole('button', { name: 'End date' })).toHaveTextContent(
      'Select end date',
    )
    expect(screen.getByTestId('filter-state')).toHaveTextContent('{}')
  })
})
