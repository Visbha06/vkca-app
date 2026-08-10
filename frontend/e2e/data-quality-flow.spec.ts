import { expect, test, type Page } from '@playwright/test'
import { installBusinessAuditApiMock } from './audit-log-fixtures'
import { installAuthApiMock } from './auth-api-mock'
import { installDataQualityApiMock } from './data-quality-fixtures'
import { installPlayersApiMock } from './players-api-mock'

const viewports = [
  { label: 'mobile', width: 320, height: 760 },
  { label: 'tablet', width: 768, height: 900 },
  { label: 'desktop', width: 1280, height: 900 },
]

async function openNavigationWhenNeeded(page: Page, width: number) {
  if (width < 768) {
    await page.getByRole('button', { name: 'Open navigation menu' }).click()
  }
}

test.describe('Data Quality', () => {
  for (const viewport of viewports) {
    test(`reviews and remediates academy health at ${viewport.label} width`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport)
      const auth = await installAuthApiMock(page)
      await installPlayersApiMock(page)
      const audit = await installBusinessAuditApiMock(page)
      const quality = await installDataQualityApiMock(page, audit)

      await page.goto('/')
      await openNavigationWhenNeeded(page, viewport.width)
      const navigation = page.getByRole('navigation', {
        name: 'Primary navigation',
      })
      await expect(
        navigation.locator('a[aria-label="Data Quality"]'),
      ).toHaveCount(1)
      const labels = await navigation.locator('a').evaluateAll((links) =>
        links.map((link) => link.getAttribute('aria-label')),
      )
      expect(labels.indexOf('Data Quality')).toBe(labels.indexOf('Audit Log') + 1)
      await navigation.getByRole('link', { name: 'Data Quality' }).click()

      await expect(page).toHaveURL(/\/data-quality$/)
      await expect(page.getByRole('heading', { name: 'Data Quality' })).toBeVisible()
      await expect(
        page.getByRole('region', { name: 'Academy health summary' }),
      ).toContainText('4')
      const headCoachFinding = page
        .getByRole('article')
        .filter({ hasText: 'Academy Head Coach coverage' })
      await expect(headCoachFinding).toContainText(/critical/i)
      await expect(headCoachFinding).toContainText('Manual review required')
      await expect(
        headCoachFinding.getByRole('button', { name: /remove/i }),
      ).toHaveCount(0)

      await page.getByRole('combobox', { name: 'Severity' }).selectOption('warning')
      await expect(page.getByRole('region', { name: 'Current findings' })).toContainText(
        'Maya Patel',
      )
      await expect(page.getByRole('article')).toHaveCount(2)
      await page.getByRole('combobox', { name: 'Domain' }).selectOption('coaches')
      await expect(page.getByRole('article')).toHaveCount(1)
      await expect(page.getByRole('article')).toContainText('Alex Morgan')
      await page.getByRole('button', { name: 'Clear filters' }).click()

      const playerFinding = page
        .getByRole('article')
        .filter({ hasText: 'Maya Patel' })
      await playerFinding.getByRole('button', { name: 'Navigate to Fix' }).click()
      await expect(page).toHaveURL(/\/players$/)
      await openNavigationWhenNeeded(page, viewport.width)
      await navigation.getByRole('link', { name: 'Data Quality' }).click()

      const assistantFinding = page
        .getByRole('article')
        .filter({ hasText: 'Alex Morgan — U13 Falcons' })
      await assistantFinding
        .getByRole('button', { name: 'Remove assignment' })
        .click()
      const dialog = page.getByRole('dialog')
      await expect(dialog).toContainText('Only this one team assignment')
      await dialog.getByRole('button', { name: 'Confirm removal' }).click()
      await expect(
        page.getByText('The inactive Assistant Coach assignment was removed.'),
      ).toBeVisible()
      await expect(
        page.getByRole('article').filter({ hasText: 'Alex Morgan' }),
      ).toHaveCount(0)
      expect(quality.assignmentPresent).toBe(false)
      expect(quality.remediationRequests).toHaveLength(1)

      await openNavigationWhenNeeded(page, viewport.width)
      await navigation.getByRole('link', { name: 'Audit Log' }).click()
      await expect(page.getByRole('heading', { name: 'Audit Log' })).toBeVisible()
      await expect(
        page.getByText('John Coach updated team assignments for Alex Morgan'),
      ).toBeVisible()

      for (const role of ['assistant coach', 'player']) {
        auth.user.role = role
        const requestsBeforeDenial = quality.qualityRequests
        await page.goto('/data-quality')
        await expect(
          page.getByRole('heading', {
            name: 'Data Quality is available to Head Coaches only.',
          }),
        ).toBeVisible()
        await expect(
          page.getByRole('link', { name: 'Data Quality' }),
        ).toHaveCount(0)
        expect(quality.qualityRequests).toBe(requestsBeforeDenial)
      }

      const hasHorizontalOverflow = await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
      )
      expect(hasHorizontalOverflow).toBe(false)
    })
  }
})
