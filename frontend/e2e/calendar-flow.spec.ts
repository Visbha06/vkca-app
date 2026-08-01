import { expect, test } from '@playwright/test'
import { installAuthApiMock } from './auth-api-mock'
import { installCalendarApiMock } from './calendar-api-mock'

test.describe('calendar coach lifecycle', () => {
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

    await page.setViewportSize({ width: 390, height: 844 })
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
