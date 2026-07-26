import { describe, expect, it } from 'vitest'
import { toApiDate, toDisplayDate } from '@shared/utils/formatDate'

describe('date formatting', () => {
  it('formats an API date without a timezone shift', () => {
    expect(toDisplayDate('1973-04-24')).toBe('24 Apr 1973')
  })

  it('formats a Date as an API calendar date', () => {
    expect(toApiDate(new Date(Date.UTC(1973, 3, 24)))).toBe('1973-04-24')
  })

  it('rejects impossible or invalid dates', () => {
    expect(() => toDisplayDate('2026-02-30')).toThrow(RangeError)
    expect(() => toDisplayDate('not-a-date')).toThrow(RangeError)
    expect(() => toApiDate(new Date(Number.NaN))).toThrow(RangeError)
  })
})
