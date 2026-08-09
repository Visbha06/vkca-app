import { expect, test } from '@playwright/test'
import { installAuthApiMock } from './auth-api-mock'
import {
  BUSINESS_AUDIT_E2E_PATH,
  installBusinessAuditApiMock,
} from './audit-log-fixtures'
import { installPlayersApiMock } from './players-api-mock'

test.describe('business audit log journey', () => {
  test('captures admin activity, reviews it newest-first, and enforces roles', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    const auth = await installAuthApiMock(page, false)
    await installPlayersApiMock(page)
    const audit = await installBusinessAuditApiMock(page)

    await page.goto('/players')
    await expect(page).toHaveURL(/\/login\?redirect=%2Fplayers$/)
    await page.getByLabel('Email address').fill('john.coach@vkca.test')
    await page.getByLabel('Password', { exact: true }).fill('CoachP@ssword1')
    await page.getByRole('button', { name: 'Log in' }).click()
    await expect(page).toHaveURL(/\/players$/)

    await page.getByRole('button', { name: /view asha singh details/i }).click()
    await page.getByRole('button', { name: 'Edit Player' }).click()
    await page
      .getByRole('textbox', { name: /^Bio/ })
      .fill('Opening batter and audit journey captain')
    await page.getByRole('button', { name: 'Save changes' }).click()
    await expect(page.getByText('Asha Singh was updated successfully.')).toBeVisible()
    await page.getByRole('button', { name: 'Close player details' }).click()

    await page.getByRole('button', { name: 'Add Player' }).click()
    await page.getByRole('textbox', { name: 'First name' }).fill('Isha')
    await page.getByRole('textbox', { name: 'Last name' }).fill('Nair')
    await page.getByRole('button', { name: 'Date of birth' }).click()
    await page.getByRole('combobox', { name: 'Year' }).selectOption('2010')
    await page.getByRole('combobox', { name: 'Month' }).selectOption('2')
    await page
      .getByRole('gridcell', { name: 'Sunday, February 14, 2010' })
      .click()
    await page.getByRole('combobox', { name: 'Batting style' }).selectOption('left')
    await page
      .getByRole('combobox', { name: 'Bowling style' })
      .selectOption('left-arm orthodox')
    await page
      .getByRole('combobox', { name: 'Player type' })
      .selectOption('all-rounder')
    await page.getByRole('button', { name: 'Create player' }).click()
    await expect(page.getByText('Isha Nair was added successfully.')).toBeVisible()

    await page.goto('/')
    const recent = page.getByRole('heading', {
      name: 'Recent academy activity',
    }).locator('..').locator('..')
    await expect(recent.getByText('John Coach added Isha Nair')).toBeVisible()
    await expect(recent.getByText('John Coach updated Asha Singh')).toBeVisible()
    await expect(recent.locator('li')).toHaveCount(4)

    await page.getByRole('link', { name: 'View all activity' }).click()
    await expect(page).toHaveURL(new RegExp(`${BUSINESS_AUDIT_E2E_PATH}$`))
    await expect(page.getByRole('heading', { name: 'Audit Log' })).toBeVisible()
    await expect(page).toHaveTitle('Audit Log | VK Cricket Academy')
    await expect(page.getByRole('option', { name: 'All categories' })).toHaveCount(1)
    await expect(page.getByRole('option', { name: 'All entities' })).toHaveCount(1)
    await expect(page.locator('input[type="date"]')).toHaveCount(0)
    await page.getByRole('button', { name: 'Start date' }).click()
    await expect(
      page.getByRole('dialog', { name: /Choose start date,/ }),
    ).toBeVisible()
    await page.keyboard.press('Escape')

    const auditItems = page
      .getByRole('region', { name: 'Business audit events' })
      .locator('li')
    await expect(auditItems).toHaveCount(4)
    await expect(auditItems.nth(0)).toContainText('John Coach added Isha Nair')
    await expect(auditItems.nth(1)).toContainText('John Coach updated Asha Singh')

    await page.getByRole('combobox', { name: 'Category' }).selectOption('player')
    await expect(auditItems).toHaveCount(2)
    await expect(page.getByRole('status').first()).toContainText('2 events found')

    const newestItem = auditItems.first()
    await newestItem.getByRole('button', { name: 'Show safe details' }).click()
    await expect(newestItem.getByText('player.created')).toBeVisible()
    await expect(newestItem.getByText('e2e-request-player-4')).toBeVisible()
    await expect(newestItem).not.toContainText('password')
    await expect(newestItem).not.toContainText('token')

    for (const role of ['assistant coach', 'player']) {
      auth.user.role = role
      const requestsBeforeDenial = audit.auditRequests
      await page.goto(BUSINESS_AUDIT_E2E_PATH)
      await expect(
        page.getByRole('heading', {
          name: 'Audit Log is available to Head Coaches only.',
        }),
      ).toBeVisible()
      await expect(page.getByRole('link', { name: 'Audit Log' })).toHaveCount(0)
      expect(audit.auditRequests).toBe(requestsBeforeDenial)
    }
  })
})
