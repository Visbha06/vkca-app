import { expect, test } from '@playwright/test'
import { installAuthApiMock } from './auth-api-mock'
import { installCalendarApiMock } from './calendar-api-mock'

test.describe('calendar coach lifecycle', () => {
  test('preserves responsive subtitle flow and mutes only adjacent-month dates', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await installAuthApiMock(page)
    await installCalendarApiMock(page)

    await page.goto('/calendar')
    const monthHeading = page.getByRole('heading', { name: 'August 2026' })
    await expect(monthHeading).toBeVisible()
    await expect(page.getByText('Academy calendar', { exact: true })).toHaveCount(0)

    const createEvent = page.getByRole('button', { name: 'Create Event' })
    const headerControls = page.getByTestId('calendar-header-controls')
    const monthNavigation = page.getByRole('group', { name: 'Month navigation' })
    const desktopLayout = await page.evaluate(() => {
      const rect = (element: Element) => {
        const { x, y, width, height } = element.getBoundingClientRect()
        return { x, y, width, height }
      }
      return {
        heading: rect(document.querySelector('#calendar-month-heading')!),
        create: rect(document.querySelector('[data-testid="calendar-header-controls"] button')!),
        year: rect(document.querySelector('[aria-label="Calendar year"]')!),
        navigation: rect(document.querySelector('[aria-label="Month navigation"]')!),
      }
    })
    expect(desktopLayout.create.x).toBeLessThan(desktopLayout.year.x)
    expect(desktopLayout.year.x).toBeLessThan(desktopLayout.navigation.x)
    expect(Math.abs(
      desktopLayout.heading.y + desktopLayout.heading.height / 2
      - (desktopLayout.create.y + desktopLayout.create.height / 2),
    )).toBeLessThan(2)
    expect(desktopLayout.create.height).toBeGreaterThanOrEqual(44)
    expect(desktopLayout.year.height).toBeGreaterThanOrEqual(44)

    const nextMonth = page.getByRole('button', { name: 'Next month' })
    await nextMonth.focus()
    await nextMonth.click()
    await expect(page.getByRole('heading', { name: 'September 2026' })).toBeVisible()
    await expect(nextMonth).toBeFocused()
    await nextMonth.click()
    await expect(page.getByRole('heading', { name: 'October 2026' })).toBeVisible()
    await expect(nextMonth).toBeFocused()

    const previousMonth = page.getByRole('button', { name: 'Previous month' })
    await previousMonth.focus()
    await previousMonth.click()
    await expect(page.getByRole('heading', { name: 'September 2026' })).toBeVisible()
    await expect(previousMonth).toBeFocused()
    await previousMonth.click()
    await expect(page.getByRole('heading', { name: 'August 2026' })).toBeVisible()
    await expect(previousMonth).toBeFocused()

    const year = page.getByRole('combobox', { name: 'Calendar year' })
    await year.focus()
    await year.selectOption('2027')
    await expect(page.getByRole('heading', { name: 'August 2027' })).toBeVisible()
    await expect(year).toBeFocused()
    await year.selectOption('2026')
    await expect(page.getByRole('heading', { name: 'August 2026' })).toBeVisible()
    await expect(page.getByRole('status')).toHaveText('August 2026 ready')
    await expect(year).toBeFocused()

    const subtitle = page.getByText(
      'Review academy events in Pacific time and keep today’s schedule close at hand.',
      { exact: true },
    )
    await expect(subtitle).toHaveCSS('white-space', 'nowrap')
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
      ),
    ).toBe(true)

    const grid = page.getByRole('grid', { name: 'August 2026 calendar' })
    const tokenColors = await page.evaluate(() => {
      const sample = document.createElement('span')
      document.body.append(sample)
      const colorFor = (className: string) => {
        sample.className = className
        return getComputedStyle(sample).color
      }
      const colors = {
        muted: colorFor('text-slate-500'),
        normal: colorFor('text-slate-800'),
        current: colorFor('text-slate-950'),
        focus: colorFor('text-slate-900'),
      }
      sample.remove()
      return colors
    })
    for (const day of [26, 27, 28, 29, 30, 31]) {
      const outsideDate = grid.getByRole('gridcell', {
        name: new RegExp(`July ${day}, 2026`),
      })
      await expect(outsideDate.locator('[data-calendar-date-number]:visible')).toHaveCSS(
        'color',
        tokenColors.muted,
      )
    }
    for (const day of [1, 2, 3, 4, 5]) {
      const outsideDate = grid.getByRole('gridcell', {
        name: new RegExp(`September ${day}, 2026`),
      })
      await expect(outsideDate.locator('[data-calendar-date-number]:visible')).toHaveCSS(
        'color',
        tokenColors.muted,
      )
    }
    for (const day of [1, 4, 31]) {
      const augustDate = grid.getByRole('gridcell', {
        name: new RegExp(`August ${day}, 2026`),
      })
      await expect(augustDate).not.toHaveAttribute('data-outside-month', 'true')
      await expect(augustDate.locator('[data-calendar-date-number]:visible')).toHaveCSS(
        'color',
        tokenColors.normal,
      )
    }
    await expect(
      grid
        .getByRole('gridcell', { name: /August 5, 2026, current academy date/ })
        .locator('[data-calendar-date-number]:visible'),
    ).toHaveCSS('color', tokenColors.current)

    const august5 = grid.getByRole('gridcell', {
      name: /August 5, 2026, current academy date/,
    })
    const august6 = grid.getByRole('gridcell', { name: /August 6, 2026/ })
    await expect(grid.locator('[aria-current="date"]')).toHaveCount(1)
    await expect(grid.locator('[aria-selected]')).toHaveCount(0)
    await august5.focus()
    const todayNumber = august5.locator('[data-calendar-date-number]:visible')
    const focusedTodayStyles = await todayNumber.evaluate((element) => {
      const styles = getComputedStyle(element)
      return {
        backgroundColor: styles.backgroundColor,
        borderColor: styles.borderColor,
        boxShadow: styles.boxShadow,
      }
    })
    expect(focusedTodayStyles.boxShadow).toContain(tokenColors.focus)
    expect(focusedTodayStyles.backgroundColor).not.toBe('rgba(0, 0, 0, 0)')
    expect(focusedTodayStyles.borderColor).not.toBe('rgba(0, 0, 0, 0)')
    await august5.press('ArrowRight')
    await expect(august6).toBeFocused()
    expect(
      await august6
        .locator('[data-calendar-date-number]:visible')
        .evaluate((element) => getComputedStyle(element).boxShadow),
    ).toContain(tokenColors.focus)
    await expect(todayNumber).toHaveCSS('box-shadow', 'none')
    await august6.press('Enter')
    await august6.press('Space')
    await expect(august6).toBeFocused()
    await expect(page.getByRole('dialog')).toHaveCount(0)

    await page.setViewportSize({ width: 390, height: 844 })
    await expect(subtitle).toHaveCSS('white-space', 'normal')
    const mobileLayout = await page.evaluate(() => {
      const rect = (element: Element) => {
        const { x, y, width, height } = element.getBoundingClientRect()
        return { x, y, width, height }
      }
      return {
        heading: rect(document.querySelector('#calendar-month-heading')!),
        controls: rect(document.querySelector('[data-testid="calendar-header-controls"]')!),
        create: rect(document.querySelector('[data-testid="calendar-header-controls"] button')!),
        year: rect(document.querySelector('[aria-label="Calendar year"]')!),
        navigation: rect(document.querySelector('[aria-label="Month navigation"]')!),
      }
    })
    expect(mobileLayout.heading.y + mobileLayout.heading.height).toBeLessThan(
      mobileLayout.create.y,
    )
    expect(mobileLayout.create.y + mobileLayout.create.height).toBeLessThan(
      mobileLayout.year.y,
    )
    expect(Math.abs(mobileLayout.year.y - mobileLayout.navigation.y)).toBeLessThan(2)
    expect(Math.abs(mobileLayout.create.width - mobileLayout.controls.width)).toBeLessThan(2)
    expect(mobileLayout.create.height).toBeGreaterThanOrEqual(44)
    expect(mobileLayout.year.height).toBeGreaterThanOrEqual(44)
    await expect(createEvent).toBeVisible()
    await expect(headerControls).toBeVisible()
    await expect(monthNavigation).toBeVisible()
    expect(
      await subtitle.evaluate(
        (element) =>
          element.clientHeight > Number.parseFloat(getComputedStyle(element).lineHeight),
      ),
    ).toBe(true)
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
      ),
    ).toBe(true)
  })

  test('creates a weekly event, edits and deletes one occurrence, then deletes the series', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await installAuthApiMock(page, false)
    const api = await installCalendarApiMock(page)

    await page.goto('/calendar')
    await expect(page).toHaveURL(/\/login\?redirect=%2Fcalendar$/)
    await page.getByLabel('Email address').fill('john.coach@vkca.test')
    await page.getByLabel('Password', { exact: true }).fill('CoachP@ssword1')
    await page.getByRole('button', { name: 'Log in' }).click()
    await expect(page).toHaveURL(/\/calendar$/)
    await expect(page.getByRole('heading', { name: 'August 2026' })).toBeVisible()

    await page.getByRole('button', { name: 'Create Event' }).click()
    const createDialog = page.getByRole('dialog', { name: 'Create event' })
    await expect(createDialog).toBeVisible()
    await createDialog.getByLabel('Event name').fill('E2E weekly practice')
    await createDialog.getByRole('checkbox', { name: 'Repeat this event' }).check()
    await createDialog
      .getByRole('button', { name: 'Create event', exact: true })
      .click()

    await expect(page.getByText('Event created.')).toBeVisible()
    expect(api.createPayloads).toHaveLength(1)
    expect(api.createPayloads[0].recurrence).toMatchObject({
      frequency: 'weekly',
      termination: 'never',
    })

    const calendarGrid = page.getByRole('grid', { name: 'August 2026 calendar' })
    const createdEntries = calendarGrid.getByRole('button', {
      name: /Practice event: E2E weekly practice/,
    })
    await expect(createdEntries).toHaveCount(5)

    const readCompactGridBounds = () => calendarGrid.evaluate((gridElement) => {
      const cells = Array.from(gridElement.querySelectorAll<HTMLElement>('[role="gridcell"]'))
      const targets = cells.map((cell) => {
        const target = cell.querySelector<HTMLElement>('[data-calendar-compact-date]')!
        const cellBounds = cell.getBoundingClientRect()
        const targetBounds = target.getBoundingClientRect()
        return {
          cellLeft: cellBounds.left,
          cellRight: cellBounds.right,
          targetLeft: targetBounds.left,
          targetRight: targetBounds.right,
          targetWidth: targetBounds.width,
          targetHeight: targetBounds.height,
        }
      })
      const detailsVisible = Array.from(
        gridElement.querySelectorAll<HTMLElement>('[data-calendar-day-details]'),
      ).filter((element) => getComputedStyle(element).display !== 'none').length
      return {
        targetCount: targets.length,
        detailsVisible,
        minimumTargetHeight: Math.min(...targets.map((target) => target.targetHeight)),
        targetsStayWithinCells: targets.every(
          (target) =>
            target.targetWidth > 0
            && target.targetLeft >= target.cellLeft - 0.5
            && target.targetRight <= target.cellRight + 0.5,
        ),
        targetsDoNotOverlap: targets.every((target, index) => {
          if (index % 7 === 6) return true
          return target.targetRight <= targets[index + 1].targetLeft + 0.5
        }),
      }
    })

    for (const width of [320, 360, 390]) {
      await page.setViewportSize({ width, height: 844 })
      const bounds = await readCompactGridBounds()
      expect(bounds.targetCount).toBe(42)
      expect(bounds.detailsVisible).toBe(0)
      expect(bounds.minimumTargetHeight).toBeGreaterThanOrEqual(44)
      expect(bounds.targetsStayWithinCells).toBe(true)
      expect(bounds.targetsDoNotOverlap).toBe(true)
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
        ),
      ).toBe(true)
    }

    const textZoomStyle = await page.addStyleTag({
      content: 'html { font-size: 200% !important; }',
    })
    const zoomedBounds = await readCompactGridBounds()
    expect(zoomedBounds.targetCount).toBe(42)
    expect(zoomedBounds.detailsVisible).toBe(0)
    expect(zoomedBounds.minimumTargetHeight).toBeGreaterThanOrEqual(44)
    expect(zoomedBounds.targetsStayWithinCells).toBe(true)
    expect(zoomedBounds.targetsDoNotOverlap).toBe(true)
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
      ),
    ).toBe(true)
    await textZoomStyle.evaluate((element) => element.parentNode?.removeChild(element))

    const compactEventDate = calendarGrid.getByRole('button', {
      name: 'View 1 event on Wednesday, August 5, 2026',
    })
    await compactEventDate.click()
    const dayEvents = page.getByRole('dialog', {
      name: 'Wednesday, August 5, 2026',
    })
    await expect(dayEvents).toBeVisible()
    await expect(
      dayEvents.getByRole('button', { name: /Practice event: E2E weekly practice/ }),
    ).toBeVisible()
    await dayEvents.getByRole('button', { name: 'Close full day events' }).click()

    await expect(page.locator('#main-content')).toHaveCSS('margin-left', '0px')
    await expect(
      page.getByRole('button', { name: 'Open navigation' }),
    ).toBeVisible()
    await page.setViewportSize({ width: 1280, height: 900 })

    await createdEntries.nth(1).click()
    const details = page.getByRole('dialog', { name: 'E2E weekly practice' })
    await details.getByRole('button', { name: 'Edit Event' }).click()

    const editDialog = page.getByRole('dialog', { name: 'Edit event' })
    await expect(
      editDialog.getByRole('radio', { name: 'This occurrence only' }),
    ).toBeChecked()
    await editDialog.getByLabel('Event name').fill('E2E moved occurrence')
    await editDialog.getByLabel('Academy date').fill('2026-08-13')
    await editDialog.getByRole('button', { name: 'Save changes' }).click()

    await expect(
      page.getByText('Occurrence updated. The rest of the series is unchanged.'),
    ).toBeVisible()
    expect(api.occurrenceUpdates).toHaveLength(1)
    await expect(
      calendarGrid.getByRole('button', { name: /Practice event: E2E moved occurrence/ }),
    ).toHaveCount(1)
    await expect(
      calendarGrid.getByRole('button', { name: /Practice event: E2E weekly practice/ }),
    ).toHaveCount(4)

    await calendarGrid
      .getByRole('button', { name: /Practice event: E2E moved occurrence/ })
      .click()
    await page
      .getByRole('dialog', { name: 'E2E moved occurrence' })
      .getByRole('button', { name: 'Delete Event' })
      .click()
    const occurrenceDelete = page.getByRole('dialog', {
      name: 'Delete E2E moved occurrence?',
    })
    await expect(
      occurrenceDelete.getByRole('radio', { name: 'This occurrence only' }),
    ).toBeChecked()
    await occurrenceDelete.getByRole('button', { name: 'Delete event' }).click()

    await expect(
      page.getByText('Occurrence deleted. The rest of the series is unchanged.'),
    ).toBeVisible()
    expect(api.occurrenceDeletes).toHaveLength(1)
    await expect(
      calendarGrid.getByRole('button', { name: /Practice event: E2E moved occurrence/ }),
    ).toHaveCount(0)
    await expect(
      calendarGrid.getByRole('button', { name: /Practice event: E2E weekly practice/ }),
    ).toHaveCount(4)

    await calendarGrid
      .getByRole('button', { name: /Practice event: E2E weekly practice/ })
      .first()
      .click()
    await page
      .getByRole('dialog', { name: 'E2E weekly practice' })
      .getByRole('button', { name: 'Delete Event' })
      .click()
    const seriesDelete = page.getByRole('dialog', {
      name: 'Delete E2E weekly practice?',
    })
    await seriesDelete.getByRole('radio', { name: 'Entire series' }).check()
    await seriesDelete
      .getByRole('button', { name: 'Delete entire series' })
      .click()

    await expect(page.getByText('Event series deleted.')).toBeVisible()
    expect(api.seriesDeletes).toBe(1)
    await expect(
      calendarGrid.getByRole('button', { name: /Practice event: E2E weekly practice/ }),
    ).toHaveCount(0)
  })
})
