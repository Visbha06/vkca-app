import { describe, expect, it } from 'vitest'
import {
  addCalendarDays,
  addCalendarMonths,
  addCalendarYears,
  calendarDateFromLocalDate,
  calendarDateToIso,
  calendarGrid,
  calendarGridRange,
  calendarGridRows,
  calendarMonthFromDate,
  calendarWeekday,
  calendarYearOptions,
  clampCalendarDate,
  compareCalendarDates,
  compareCalendarMonths,
  daysInCalendarMonth,
  formatAcademyDate,
  formatAcademyDateLabel,
  isCalendarDateInMonth,
  isSameCalendarDate,
  moveCalendarFocus,
  parseAcademyDate,
  parseCalendarDate,
} from '@shared/utils/calendarDate'

describe('calendar date utilities', () => {
  it('parses and serializes valid ISO calendar dates', () => {
    const date = parseCalendarDate('2005-08-17')
    expect(date).toEqual({ year: 2005, month: 8, day: 17 })
    expect(calendarDateToIso(date!)).toBe('2005-08-17')
    expect(calendarMonthFromDate(date!)).toEqual({ year: 2005, month: 8 })
  })

  it('rejects malformed and impossible calendar dates', () => {
    expect(parseCalendarDate('2005-8-17')).toBeNull()
    expect(parseCalendarDate('2025-02-29')).toBeNull()
    expect(parseCalendarDate('2024-02-29')).toEqual({
      year: 2024,
      month: 2,
      day: 29,
    })
    expect(() =>
      calendarDateToIso({ year: 2025, month: 2, day: 29 }),
    ).toThrow(RangeError)
  })

  it('calculates February and leap-year boundaries', () => {
    expect(daysInCalendarMonth(2024, 2)).toBe(29)
    expect(daysInCalendarMonth(2025, 2)).toBe(28)
    expect(
      addCalendarYears({ year: 2024, month: 2, day: 29 }, 1),
    ).toEqual({ year: 2025, month: 2, day: 28 })
  })

  it('moves across day and month boundaries without invalid dates', () => {
    expect(addCalendarDays({ year: 2025, month: 8, day: 31 }, 1)).toEqual({
      year: 2025,
      month: 9,
      day: 1,
    })
    expect(
      addCalendarMonths({ year: 2025, month: 1, day: 31 }, 1),
    ).toEqual({ year: 2025, month: 2, day: 28 })
  })

  it('compares, clamps, and identifies calendar dates and months', () => {
    const range = {
      earliest: { year: 1926, month: 7, day: 27 },
      latest: { year: 2026, month: 7, day: 27 },
    }
    expect(
      compareCalendarDates(range.earliest, range.latest),
    ).toBeLessThan(0)
    expect(
      compareCalendarMonths(
        { year: 2026, month: 6 },
        { year: 2026, month: 7 },
      ),
    ).toBeLessThan(0)
    expect(
      clampCalendarDate({ year: 1900, month: 1, day: 1 }, range),
    ).toEqual(range.earliest)
    expect(isSameCalendarDate(range.latest, { ...range.latest })).toBe(true)
    expect(isSameCalendarDate(range.latest, null)).toBe(false)
  })

  it('builds a six-week Sunday-first calendar grid', () => {
    const grid = calendarGrid({ year: 2025, month: 8 })
    expect(grid).toHaveLength(42)
    expect(grid[0]).toEqual({ year: 2025, month: 7, day: 27 })
    expect(grid[41]).toEqual({ year: 2025, month: 9, day: 6 })
  })

  it('uses only the complete week rows required by each month', () => {
    expect(calendarGrid({ year: 2026, month: 2 })).toHaveLength(28)
    expect(calendarGrid({ year: 2026, month: 7 })).toHaveLength(35)
    expect(calendarGrid({ year: 2024, month: 2 })).toHaveLength(35)
    expect(calendarGrid({ year: 2025, month: 8 })).toHaveLength(42)
  })

  it('returns complete rows and an inclusive visible grid range', () => {
    const rows = calendarGridRows({ year: 2026, month: 8 })
    expect(rows).toHaveLength(6)
    expect(rows.every((row) => row.length === 7)).toBe(true)
    expect(calendarGridRange({ year: 2026, month: 8 })).toEqual({
      earliest: { year: 2026, month: 7, day: 26 },
      latest: { year: 2026, month: 9, day: 5 },
    })
    expect(
      isCalendarDateInMonth(
        { year: 2026, month: 8, day: 31 },
        { year: 2026, month: 8 },
      ),
    ).toBe(true)
    expect(
      isCalendarDateInMonth(
        { year: 2026, month: 9, day: 1 },
        { year: 2026, month: 8 },
      ),
    ).toBe(false)
  })

  it('parses, serializes, and labels academy-local dates without drift', () => {
    const academyDate = parseAcademyDate('2026-08-05')
    expect(academyDate).toEqual({ year: 2026, month: 8, day: 5 })
    expect(formatAcademyDate(academyDate!)).toBe('2026-08-05')
    expect(formatAcademyDateLabel(academyDate!)).toBe(
      'Wednesday, August 5, 2026',
    )
  })

  it('calculates keyboard focus movement across week and month edges', () => {
    const monday = { year: 2026, month: 8, day: 31 }
    expect(calendarWeekday(monday)).toBe(1)
    expect(moveCalendarFocus(monday, 'ArrowLeft')).toEqual({
      year: 2026,
      month: 8,
      day: 30,
    })
    expect(moveCalendarFocus(monday, 'ArrowRight')).toEqual({
      year: 2026,
      month: 9,
      day: 1,
    })
    expect(moveCalendarFocus(monday, 'ArrowUp')).toEqual({
      year: 2026,
      month: 8,
      day: 24,
    })
    expect(moveCalendarFocus(monday, 'ArrowDown')).toEqual({
      year: 2026,
      month: 9,
      day: 7,
    })
    expect(moveCalendarFocus(monday, 'Home')).toEqual({
      year: 2026,
      month: 8,
      day: 30,
    })
    expect(moveCalendarFocus(monday, 'End')).toEqual({
      year: 2026,
      month: 9,
      day: 5,
    })
  })

  it('builds the dynamic 2026 through academy-year-plus-five options', () => {
    expect(calendarYearOptions({ year: 2026, month: 8, day: 1 })).toEqual([
      2026,
      2027,
      2028,
      2029,
      2030,
      2031,
    ])
    expect(calendarYearOptions({ year: 2030, month: 1, day: 1 })).toEqual([
      2026,
      2027,
      2028,
      2029,
      2030,
      2031,
      2032,
      2033,
      2034,
      2035,
    ])
  })

  it('orders unique dates without ever generating a seventh week', () => {
    const startingWeekdays = new Set<number>()
    const monthLengths = new Set<number>()
    const renderedCellCounts = new Set<number>()

    for (let year = 2020; year <= 2035; year += 1) {
      for (let month = 1; month <= 12; month += 1) {
        const grid = calendarGrid({ year, month })
        const isoDates = grid.map(calendarDateToIso)
        const firstOfMonthIndex = grid.findIndex(
          (date) =>
            date.year === year &&
            date.month === month &&
            date.day === 1,
        )
        startingWeekdays.add(firstOfMonthIndex)
        monthLengths.add(daysInCalendarMonth(year, month))
        renderedCellCounts.add(grid.length)

        expect(grid.length % 7).toBe(0)
        expect(grid.length).toBeLessThanOrEqual(42)
        expect(new Set(isoDates).size).toBe(grid.length)
        for (let index = 1; index < grid.length; index += 1) {
          expect(grid[index]).toEqual(addCalendarDays(grid[index - 1], 1))
        }
      }
    }

    expect(startingWeekdays).toEqual(new Set([0, 1, 2, 3, 4, 5, 6]))
    expect(monthLengths).toEqual(new Set([28, 29, 30, 31]))
    expect(renderedCellCounts).toEqual(new Set([28, 35, 42]))
  })

  it('reads local calendar parts without parsing an ISO timestamp', () => {
    expect(
      calendarDateFromLocalDate(new Date(2026, 6, 27, 23, 30)),
    ).toEqual({ year: 2026, month: 7, day: 27 })
  })
})
