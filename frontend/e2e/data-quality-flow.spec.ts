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
      const pageHeading = page.getByRole('heading', { name: 'Data Quality' })
      await expect(pageHeading).toBeVisible()
      await expect(pageHeading).toBeFocused()
      await expect(pageHeading).toHaveAttribute('tabindex', '-1')
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

      const ruleFilter = page.getByRole('combobox', { name: 'Rule' })
      await expect(
        ruleFilter.locator('option[value="coach.inactive_assigned"]'),
      ).toHaveText('Inactive Assistant Coach still assigned')
      await expect(ruleFilter).not.toContainText('coach.inactive_assigned')

      const canonicalRuleRequest = page.waitForRequest((request) => {
        const url = new URL(request.url())
        return url.pathname === '/api/v1/data-quality'
          && url.searchParams.get('rule_id') === 'coach.inactive_assigned'
      })
      await ruleFilter.selectOption({ label: 'Inactive Assistant Coach still assigned' })
      await canonicalRuleRequest
      await expect(page.getByRole('article')).toHaveCount(1)
      await expect(page.getByRole('article')).toContainText('Alex Morgan')

      const allRulesRequest = page.waitForRequest((request) => {
        const url = new URL(request.url())
        return url.pathname === '/api/v1/data-quality'
          && !url.searchParams.has('rule_id')
      })
      await ruleFilter.selectOption({ label: 'All rules' })
      await allRulesRequest
      await expect(page.getByRole('article')).toHaveCount(4)

      const filtersHaveHorizontalOverflow = await page
        .getByRole('region', { name: 'Finding filters' })
        .evaluate((filters) => filters.scrollWidth > filters.clientWidth)
      expect(filtersHaveHorizontalOverflow).toBe(false)

      const filterPositions = await page
        .getByRole('region', { name: 'Finding filters' })
        .evaluate((filters) => {
          const controls = ['Severity', 'Domain', 'Rule', 'Clear filters'].map(
            (label) => {
              const control = filters.querySelector<HTMLElement>(
                `[aria-label="${label}"]`,
              )
                ?? Array.from(filters.querySelectorAll<HTMLElement>('button'))
                  .find((button) => button.textContent === label)
              if (!control) throw new Error(`Missing ${label} filter control`)
              const bounds = control.getBoundingClientRect()
              return { left: bounds.left, top: bounds.top }
            },
          )
          return controls
        })

      if (viewport.width === 320) {
        expect(new Set(filterPositions.map(({ top }) => top)).size).toBe(4)
      } else if (viewport.width === 768) {
        expect(filterPositions[0]?.top).toBe(filterPositions[1]?.top)
        expect(filterPositions[2]?.top).toBe(filterPositions[3]?.top)
        expect(filterPositions[0]?.left).toBe(filterPositions[2]?.left)
        expect(filterPositions[1]?.left).toBe(filterPositions[3]?.left)
      } else {
        expect(new Set(filterPositions.map(({ top }) => top)).size).toBe(1)
      }

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
