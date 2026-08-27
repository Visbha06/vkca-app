import { describe, expect, it } from 'vitest'
import {
  formatBusinessAuditRelativeTime,
  formatBusinessAuditShortDate,
  formatBusinessAuditTimestamp,
} from './businessAuditTime'

describe('business audit academy time', () => {
  it('formats stored instants on both sides of the spring DST transition', () => {
    expect(formatBusinessAuditTimestamp('2026-03-08T09:30:00Z')).toContain(
      'Mar 8, 2026, 1:30 AM',
    )
    expect(formatBusinessAuditTimestamp('2026-03-08T10:30:00Z')).toContain(
      'Mar 8, 2026, 3:30 AM',
    )
  })

  it('uses academy calendar dates for Yesterday across short and long DST days', () => {
    expect(
      formatBusinessAuditRelativeTime(
        '2026-03-08T09:30:00Z',
        '2026-03-09T08:30:00Z',
      ),
    ).toBe('Yesterday')
    expect(
      formatBusinessAuditRelativeTime(
        '2026-11-01T08:30:00Z',
        '2026-11-02T09:30:00Z',
      ),
    ).toBe('Yesterday')
  })

  it('formats compact dates using the academy date at UTC boundaries', () => {
    expect(formatBusinessAuditShortDate('2026-01-01T07:30:00Z')).toBe('Dec 31')
    expect(formatBusinessAuditShortDate('2026-03-08T07:30:00Z')).toBe('Mar 7')
    expect(formatBusinessAuditShortDate('2026-03-08T08:30:00Z')).toBe('Mar 8')
  })

  it('formats same-day relative minutes and hours', () => {
    expect(
      formatBusinessAuditRelativeTime(
        '2026-08-05T18:00:00Z',
        '2026-08-05T20:00:00Z',
      ),
    ).toBe('2 hours ago')
    expect(
      formatBusinessAuditRelativeTime(
        '2026-08-05T19:45:00Z',
        '2026-08-05T20:00:00Z',
      ),
    ).toBe('15 minutes ago')
  })
})
