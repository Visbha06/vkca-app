// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { CalendarEventCreatePayload } from '../types/calendar'
import EventForm from './EventForm'

function values(
  overrides: Partial<CalendarEventCreatePayload> = {},
): CalendarEventCreatePayload {
  return {
    event_type: 'practice',
    name: 'Wednesday practice',
    event_date: '2026-08-05',
    is_all_day: false,
    start_time: '17:00',
    end_time: '18:30',
    scope: { scope_kind: 'age_group', age_groups: ['U13'] },
    recurrence: null,
    ...overrides,
  }
}

function renderForm(
  initialValues = values(),
  options: {
    allowRecurrence?: boolean
    allowUnchangedPast?: boolean
    onSubmit?: ReturnType<typeof vi.fn>
  } = {},
) {
  const onSubmit = options.onSubmit ?? vi.fn()
  const onDirtyChange = vi.fn()
  render(
    <EventForm
      initialValues={initialValues}
      academyToday="2026-08-01"
      allowRecurrence={options.allowRecurrence ?? true}
      allowUnchangedPast={options.allowUnchangedPast}
      isSubmitting={false}
      errorMessage={null}
      submitLabel="Save event"
      onCancel={vi.fn()}
      onDirtyChange={onDirtyChange}
      onSubmit={onSubmit}
    />,
  )
  return { onDirtyChange, onSubmit }
}

afterEach(cleanup)

describe('EventForm', () => {
  it('validates required names, same-day times, past dates, and scope', () => {
    const { onSubmit } = renderForm(
      values({
        name: '',
        event_date: '2026-07-31',
        start_time: '18:30',
        end_time: '18:00',
        scope: { scope_kind: 'age_group', age_groups: [] },
      }),
    )

    fireEvent.click(screen.getByRole('button', { name: 'Save event' }))

    expect(screen.getByText('Enter an event name.')).toBeVisible()
    expect(screen.getByText('Choose an academy date that has not passed.')).toBeVisible()
    expect(screen.getByText('Enter a start time and a later end time.')).toBeVisible()
    expect(screen.getByText('Select at least one age group or choose All Academy.')).toBeVisible()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('supports Miscellaneous all-day and unambiguous All Academy values', () => {
    const { onSubmit } = renderForm()

    fireEvent.change(screen.getByLabelText('Event type'), {
      target: { value: 'miscellaneous' },
    })
    fireEvent.click(screen.getByRole('checkbox', { name: 'All-day event' }))
    fireEvent.click(screen.getByRole('checkbox', { name: 'All Academy' }))
    expect(screen.queryByLabelText('Start time')).not.toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'U13' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Save event' }))

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        event_type: 'miscellaneous',
        is_all_day: true,
        start_time: null,
        end_time: null,
        scope: { scope_kind: 'all_academy', age_groups: [] },
      }),
    )
  })

  it('shows accessible recurrence termination fields and tracks dirty state', () => {
    const { onDirtyChange } = renderForm()

    fireEvent.click(screen.getByRole('checkbox', { name: 'Repeat this event' }))
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Recurrence frequency' }),
      { target: { value: 'yearly' } },
    )
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Recurrence termination' }),
      { target: { value: 'occurrence_count' } },
    )

    expect(screen.getByLabelText('Number of occurrences')).toHaveValue(2)
    expect(onDirtyChange).toHaveBeenLastCalledWith(true)
  })

  it('allows non-schedule edits to an unchanged historical event', () => {
    const { onSubmit } = renderForm(
      values({ event_date: '2026-07-31' }),
      { allowUnchangedPast: true },
    )

    fireEvent.change(screen.getByLabelText('Event name'), {
      target: { value: 'Corrected historical practice' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save event' }))

    expect(screen.queryByText('Choose an academy date that has not passed.')).not.toBeInTheDocument()
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Corrected historical practice',
        event_date: '2026-07-31',
      }),
    )
  })
})
