// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClientError } from '@shared/api/client'
import {
  createCalendarEvent,
  fetchCalendarInstance,
  updateCalendarOccurrence,
  updateCalendarSeries,
} from '../api/calendarApi'
import type { CalendarEventInstance } from '../types/calendar'
import EventFormModal from './EventFormModal'

vi.mock('../api/calendarApi', () => ({
  createCalendarEvent: vi.fn(),
  updateStandaloneCalendarEvent: vi.fn(),
  updateCalendarOccurrence: vi.fn(),
  updateCalendarSeries: vi.fn(),
  fetchCalendarInstance: vi.fn(),
}))

const mockedCreate = vi.mocked(createCalendarEvent)
const mockedFetchInstance = vi.mocked(fetchCalendarInstance)
const mockedUpdateOccurrence = vi.mocked(updateCalendarOccurrence)
const mockedUpdateSeries = vi.mocked(updateCalendarSeries)

function recurringEvent(): CalendarEventInstance {
  const recurrence = {
    id: '11111111-1111-4111-8111-111111111111',
    event_id: '22222222-2222-4222-8222-222222222222',
    frequency: 'weekly' as const,
    termination: 'never' as const,
    end_date: null,
    occurrence_count: null,
    weekday: 2,
    month: null,
    month_day: null,
    created_at: '2026-08-01T12:00:00Z',
    updated_at: '2026-08-01T12:00:00Z',
  }
  return {
    occurrence_id: '11111111-1111-4111-8111-111111111111:2026-08-05',
    event_id: '22222222-2222-4222-8222-222222222222',
    series_id: '11111111-1111-4111-8111-111111111111',
    original_date: '2026-08-05',
    event_date: '2026-08-05',
    event_type: 'practice',
    name: 'Wednesday practice',
    is_all_day: false,
    start_time: '17:00:00',
    end_time: '18:30:00',
    scope_kind: 'age_group',
    age_groups: ['U13'],
    is_recurring: true,
    recurrence_summary: 'Every week on Wednesday',
    series_definition: {
      id: '22222222-2222-4222-8222-222222222222',
      event_type: 'practice',
      name: 'Wednesday practice',
      event_date: '2026-08-05',
      is_all_day: false,
      start_time: '17:00:00',
      end_time: '18:30:00',
      scope: { scope_kind: 'age_group', age_groups: ['U13'] },
      version_number: 2,
      recurrence,
      created_at: '2026-08-01T12:00:00Z',
      updated_at: '2026-08-01T12:00:00Z',
    },
    event_version_number: 2,
    exception_id: null,
    exception_version_number: null,
  }
}

afterEach(() => {
  cleanup()
  vi.resetAllMocks()
})

describe('EventFormModal', () => {
  it('creates a valid event once and reports success', async () => {
    mockedCreate.mockResolvedValue({} as never)
    const onSaved = vi.fn()
    render(
      <EventFormModal
        academyToday="2026-08-01"
        onClose={vi.fn()}
        onSaved={onSaved}
        onEventReloaded={vi.fn()}
      />,
    )

    fireEvent.change(screen.getByLabelText('Event name'), {
      target: { value: 'New practice' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create event' }))

    await waitFor(() => expect(mockedCreate).toHaveBeenCalledOnce())
    expect(onSaved).toHaveBeenCalledWith('Event created.')
  })

  it('defaults recurring edits to one occurrence and sends both versions', async () => {
    mockedUpdateOccurrence.mockResolvedValue(recurringEvent())
    const event = recurringEvent()
    render(
      <EventFormModal
        academyToday="2026-08-01"
        event={event}
        onClose={vi.fn()}
        onSaved={vi.fn()}
        onEventReloaded={vi.fn()}
      />,
    )

    expect(screen.getByRole('radio', { name: 'This occurrence only' })).toBeChecked()
    fireEvent.change(screen.getByLabelText('Event name'), {
      target: { value: 'Occurrence practice' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    await waitFor(() => expect(mockedUpdateOccurrence).toHaveBeenCalledOnce())
    expect(mockedUpdateOccurrence).toHaveBeenCalledWith(
      event.occurrence_id,
      expect.objectContaining({
        name: 'Occurrence practice',
        version_number: 2,
        exception_version_number: null,
      }),
    )
  })

  it('requires explicit confirmation before removing series exceptions', async () => {
    mockedUpdateSeries
      .mockRejectedValueOnce(
        new ApiClientError(422, {
          detail: 'internal detail',
          code: 'exception_removal_confirmation_required',
          removed_exception_original_dates: ['2026-08-05'],
        }),
      )
      .mockResolvedValueOnce({} as never)
    const onSaved = vi.fn()
    render(
      <EventFormModal
        academyToday="2026-08-01"
        event={recurringEvent()}
        onClose={vi.fn()}
        onSaved={onSaved}
        onEventReloaded={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('radio', { name: 'Entire series' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(
      await screen.findByRole('alertdialog', {
        name: 'Remove saved occurrence changes?',
      }),
    ).toBeVisible()
    fireEvent.click(
      screen.getByRole('button', { name: 'Continue and remove changes' }),
    )

    await waitFor(() => expect(mockedUpdateSeries).toHaveBeenCalledTimes(2))
    expect(mockedUpdateSeries.mock.calls[0][1]).toMatchObject({
      confirm_exception_removals: false,
    })
    expect(mockedUpdateSeries.mock.calls[1][1]).toMatchObject({
      confirm_exception_removals: true,
    })
    expect(onSaved).toHaveBeenCalledWith('Event series updated.')
  })

  it('seeds entire-series edits from the owning definition', async () => {
    mockedUpdateSeries.mockResolvedValue({} as never)
    const event = recurringEvent()
    event.name = 'Occurrence-only name'
    event.event_date = '2026-08-06'

    render(
      <EventFormModal
        academyToday="2026-08-01"
        event={event}
        onClose={vi.fn()}
        onSaved={vi.fn()}
        onEventReloaded={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('Event name')).toHaveValue('Occurrence-only name')
    fireEvent.click(screen.getByRole('radio', { name: 'Entire series' }))
    expect(screen.getByLabelText('Event name')).toHaveValue('Wednesday practice')
    expect(screen.getByLabelText('Academy date')).toHaveValue('2026-08-05')
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    await waitFor(() => expect(mockedUpdateSeries).toHaveBeenCalledOnce())
    expect(mockedUpdateSeries.mock.calls[0][1]).toMatchObject({
      name: 'Wednesday practice',
      event_date: '2026-08-05',
    })
  })

  it('uses safe permission copy and preserves entered values after failure', async () => {
    mockedCreate.mockRejectedValue(
      new ApiClientError(403, {
        detail: 'raw authorization middleware detail',
      }),
    )
    render(
      <EventFormModal
        academyToday="2026-08-01"
        onClose={vi.fn()}
        onSaved={vi.fn()}
        onEventReloaded={vi.fn()}
      />,
    )

    const nameInput = screen.getByLabelText('Event name')
    fireEvent.change(nameInput, { target: { value: 'Keep this practice' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create event' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'You do not have permission to make this calendar change.',
    )
    expect(screen.getByLabelText('Event name')).toHaveValue('Keep this practice')
    expect(screen.getByRole('alert')).not.toHaveTextContent('middleware')
  })

  it('offers one explicit reload after a conflict without retrying the mutation', async () => {
    const event = recurringEvent()
    mockedUpdateOccurrence.mockRejectedValue(
      new ApiClientError(409, {
        detail: 'raw stale write detail',
        code: 'calendar_stale_version',
      }),
    )
    mockedFetchInstance.mockResolvedValue({
      ...event,
      name: 'Latest practice from server',
      event_version_number: 3,
    })
    const onEventReloaded = vi.fn()
    render(
      <EventFormModal
        academyToday="2026-08-01"
        event={event}
        onClose={vi.fn()}
        onSaved={vi.fn()}
        onEventReloaded={onEventReloaded}
      />,
    )

    fireEvent.change(screen.getByLabelText('Event name'), {
      target: { value: 'Conflicting local edit' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    const reload = await screen.findByRole('button', {
      name: 'Reload latest event',
    })
    expect(mockedUpdateOccurrence).toHaveBeenCalledOnce()
    expect(screen.getByRole('alert')).not.toHaveTextContent('raw stale')

    fireEvent.click(reload)

    await waitFor(() => {
      expect(screen.getByLabelText('Event name')).toHaveValue(
        'Latest practice from server',
      )
    })
    expect(mockedUpdateOccurrence).toHaveBeenCalledOnce()
    expect(mockedFetchInstance).toHaveBeenCalledOnce()
    expect(onEventReloaded).toHaveBeenCalledOnce()
  })

  it('cancels an exception-removal warning without losing the series draft', async () => {
    mockedUpdateSeries.mockRejectedValue(
      new ApiClientError(422, {
        detail: 'internal detail',
        code: 'exception_removal_confirmation_required',
        removed_exception_original_dates: ['2026-08-12'],
      }),
    )
    render(
      <EventFormModal
        academyToday="2026-08-01"
        event={recurringEvent()}
        onClose={vi.fn()}
        onSaved={vi.fn()}
        onEventReloaded={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('radio', { name: 'Entire series' }))
    fireEvent.change(screen.getByLabelText('Event name'), {
      target: { value: 'Preserved series draft' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    await screen.findByRole('alertdialog', {
      name: 'Remove saved occurrence changes?',
    })

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.getByLabelText('Event name')).toHaveValue(
      'Preserved series draft',
    )
  })

  it('blocks repeated submission while the first mutation is in flight', async () => {
    let resolveCreate: (() => void) | undefined
    mockedCreate.mockImplementation(
      () => new Promise((resolve) => { resolveCreate = () => resolve({} as never) }),
    )
    render(
      <EventFormModal
        academyToday="2026-08-01"
        onClose={vi.fn()}
        onSaved={vi.fn()}
        onEventReloaded={vi.fn()}
      />,
    )

    fireEvent.change(screen.getByLabelText('Event name'), {
      target: { value: 'One submission only' },
    })
    const submit = screen.getByRole('button', { name: 'Create event' })
    fireEvent.click(submit)
    fireEvent.click(submit)

    expect(mockedCreate).toHaveBeenCalledOnce()
    expect(screen.getByRole('button', { name: 'Saving event…' })).toBeDisabled()

    await waitFor(async () => {
      resolveCreate?.()
      expect(mockedCreate).toHaveBeenCalledOnce()
    })
  })

  it('uses an accessible discard confirmation and can continue editing', () => {
    const onClose = vi.fn()
    render(
      <EventFormModal
        academyToday="2026-08-01"
        onClose={onClose}
        onSaved={vi.fn()}
        onEventReloaded={vi.fn()}
      />,
    )

    fireEvent.change(screen.getByLabelText('Event name'), {
      target: { value: 'Unsaved practice' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Close create event' }))

    expect(
      screen.getByRole('alertdialog', { name: 'Discard unsaved changes?' }),
    ).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Continue editing' }))
    expect(onClose).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Event name')).toHaveValue('Unsaved practice')

    fireEvent.click(screen.getByRole('button', { name: 'Close create event' }))
    fireEvent.click(screen.getByRole('button', { name: 'Discard changes' }))
    expect(onClose).toHaveBeenCalledOnce()
  })
})
