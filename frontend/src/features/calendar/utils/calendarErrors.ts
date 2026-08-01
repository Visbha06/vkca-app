import { ApiClientError } from '@shared/api/client'
import { parseAcademyDate } from '@shared/utils/calendarDate'
import type {
  CalendarApiError,
  CalendarErrorCode,
  ExceptionRemovalWarningResponse,
} from '../types/calendar'

const DEFAULT_CALENDAR_ERROR =
  'Unable to complete the calendar request. Please try again.'

const CALENDAR_ERROR_MESSAGES: Record<CalendarErrorCode, string> = {
  calendar_range_too_large:
    'Unable to load that calendar range. Choose a shorter range and try again.',
  calendar_event_in_past:
    'Choose an academy date and time that has not passed.',
  calendar_event_times_invalid:
    'Enter a start time and a later end time on the same academy day.',
  calendar_scope_invalid:
    'Select at least one age group or choose All Academy.',
  calendar_recurrence_invalid:
    'Check the recurrence details and try again.',
  exception_removal_confirmation_required:
    'Review the affected occurrence changes before continuing.',
  calendar_stale_version:
    'This event changed since you opened it. Reload before trying again.',
}

const CALENDAR_ERROR_CODES = new Set<CalendarErrorCode>(
  Object.keys(CALENDAR_ERROR_MESSAGES) as CalendarErrorCode[],
)

export type CalendarRecoveryAction = 'none' | 'reload' | 'retry'

export interface CalendarErrorPresentation {
  message: string
  recoveryAction: CalendarRecoveryAction
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isCalendarErrorCode(value: unknown): value is CalendarErrorCode {
  return (
    typeof value === 'string' &&
    CALENDAR_ERROR_CODES.has(value as CalendarErrorCode)
  )
}

export function isCalendarApiError(value: unknown): value is CalendarApiError {
  if (!isRecord(value) || typeof value.detail !== 'string') return false
  return value.code === null || isCalendarErrorCode(value.code)
}

export function getCalendarErrorCode(
  error: unknown,
): CalendarErrorCode | null {
  if (!(error instanceof ApiClientError) || !isCalendarApiError(error.body)) {
    return null
  }
  return error.body.code
}

export function getCalendarErrorMessage(
  error: unknown,
  fallback = DEFAULT_CALENDAR_ERROR,
) {
  return getCalendarErrorPresentation(error, fallback).message
}

export function getCalendarErrorPresentation(
  error: unknown,
  fallback = DEFAULT_CALENDAR_ERROR,
): CalendarErrorPresentation {
  const code = getCalendarErrorCode(error)
  if (code !== null) {
    return {
      message: CALENDAR_ERROR_MESSAGES[code],
      recoveryAction:
        code === 'calendar_stale_version' ? 'reload' : 'none',
    }
  }

  if (error instanceof ApiClientError) {
    if (error.status === 403) {
      return {
        message: 'You do not have permission to make this calendar change.',
        recoveryAction: 'none',
      }
    }
    if (error.status === 404) {
      return {
        message: 'This calendar event is no longer available.',
        recoveryAction: 'none',
      }
    }
    if (error.status === 409) {
      return {
        message: CALENDAR_ERROR_MESSAGES.calendar_stale_version,
        recoveryAction: 'reload',
      }
    }
    if (error.status === 429) {
      return {
        message: 'Too many calendar requests. Please wait and try again.',
        recoveryAction: 'retry',
      }
    }
    if (error.status === 400 || error.status === 422) {
      return {
        message: 'Check the calendar details and try again.',
        recoveryAction: 'none',
      }
    }
  }

  return { message: fallback, recoveryAction: 'retry' }
}

export function isExceptionRemovalWarning(
  value: unknown,
): value is ExceptionRemovalWarningResponse {
  if (
    !isRecord(value) ||
    value.code !== 'exception_removal_confirmation_required' ||
    typeof value.detail !== 'string' ||
    !Array.isArray(value.removed_exception_original_dates)
  ) {
    return false
  }
  return value.removed_exception_original_dates.every(
    (candidate) =>
      typeof candidate === 'string' && parseAcademyDate(candidate) !== null,
  )
}

export function getExceptionRemovalWarning(
  error: unknown,
): ExceptionRemovalWarningResponse | null {
  if (
    !(error instanceof ApiClientError) ||
    error.status !== 422 ||
    !isExceptionRemovalWarning(error.body)
  ) {
    return null
  }

  const removedDates = [...error.body.removed_exception_original_dates]
  const occurrenceLabel = removedDates.length === 1 ? 'occurrence' : 'occurrences'
  return {
    code: 'exception_removal_confirmation_required',
    detail: `This change will remove saved changes for ${removedDates.length} ${occurrenceLabel}.`,
    removed_exception_original_dates: removedDates,
  }
}
