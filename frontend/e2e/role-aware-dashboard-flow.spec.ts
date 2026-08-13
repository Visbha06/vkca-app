import { expect, test, type Locator, type Page } from '@playwright/test'
import { installAuthApiMock } from './auth-api-mock'
import { installPlayersApiMock } from './players-api-mock'
import {
  installRoleAwareDashboardApiMock,
  type DashboardFixtureRole,
} from './role-aware-dashboard-fixtures'

const viewports = [
  { label: 'mobile', width: 320, height: 760 },
  { label: 'tablet', width: 768, height: 900 },
  { label: 'compact desktop', width: 1024, height: 900 },
  { label: 'desktop', width: 1280, height: 900 },
  { label: 'wide desktop', width: 2560, height: 1200 },
]

async function expectOnePrimaryAction(page: Page, name: string) {
  const primaryNavigation = page.getByRole('navigation', {
    name: 'Primary action',
  })
  await expect(primaryNavigation.getByRole('link')).toHaveCount(1)
  await expect(primaryNavigation.getByRole('link')).toHaveAccessibleName(name)
  await expect(primaryNavigation).not.toContainText('Create match')
}

async function expectMinimumTarget(locator: Locator) {
  const bounds = await locator.boundingBox()
  expect(bounds).not.toBeNull()
  expect(bounds!.height).toBeGreaterThanOrEqual(44)
  expect(bounds!.width).toBeGreaterThanOrEqual(44)
}

test.describe('role-aware dashboard journey', () => {
  test('isolates all roles, actions, empty fallback, and retry states', async ({
    page,
  }) => {
    const auth = await installAuthApiMock(page)
    await installPlayersApiMock(page)
    const api = await installRoleAwareDashboardApiMock(page, auth)

    const roleChecks: Array<{
      role: DashboardFixtureRole
      action: string
      context: string
    }> = [
      {
        role: 'head coach',
        action: 'Schedule event',
        context: 'Recent academy activity',
      },
      {
        role: 'assistant coach',
        action: 'Schedule event',
        context: 'My teams',
      },
      {
        role: 'player',
        action: 'View Upcoming Events',
        context: 'My teams',
      },
      {
        role: 'unlinked player',
        action: 'View Upcoming Events',
        context: 'My teams',
      },
    ]

    for (const check of roleChecks) {
      api.emptyEvents = false
      api.setRole(check.role)
      await page.goto('/')
      await expect(
        page.getByRole('heading', { level: 1, name: /Welcome back/ }),
      ).toBeVisible()
      await expectOnePrimaryAction(page, check.action)
      await expect(
        page.getByRole('region', { name: check.context }),
      ).toBeVisible()

      if (check.role === 'head coach') {
        await expect(
          page
            .getByRole('region', { name: 'Recent academy activity' })
            .getByRole('listitem'),
        ).toHaveCount(4)
        await expect(
          page.getByRole('region', { name: 'Upcoming events' }).getByRole('listitem'),
        ).toHaveCount(5)
      } else {
        await expect(
          page.getByRole('region', { name: 'Recent academy activity' }),
        ).toHaveCount(0)
      }

      if (check.role === 'unlinked player') {
        await expect(page.getByText(/Contact your Head Coach/).first()).toBeVisible()
        await expect(page.getByText('Northside CC')).toHaveCount(0)
        await expect(page.getByText('42', { exact: true })).toHaveCount(0)
      } else if (check.role !== 'head coach') {
        await expect(page.getByText('011 Junior Restricted Practice')).toHaveCount(0)
      }
    }

    api.setRole('player')
    api.emptyEvents = true
    await page.goto('/')
    await expectOnePrimaryAction(page, 'View Teams')
    await expect(
      page.getByRole('link', { name: 'View Teams', exact: true }),
    ).toHaveAttribute('href', '/teams')

    api.setRole('head coach')
    api.emptyEvents = false
    api.failNextDashboard = true
    await page.goto('/')
    await expect(page.getByRole('alert')).toContainText(
      'Your briefing is unavailable',
    )
    api.failNextDashboard = false
    await page.getByRole('button', { name: 'Retry dashboard' }).click()
    await expect(page.getByText('Northside CC')).toBeVisible()
    expect(api.dashboardRequests).toBeGreaterThanOrEqual(6)
    expect(api.matchManagementRequests).toBe(0)
  })

  test('links an exact Player account inside the existing Player Directory', async ({
    page,
  }) => {
    const auth = await installAuthApiMock(page)
    await installPlayersApiMock(page)
    const api = await installRoleAwareDashboardApiMock(page, auth)
    api.setRole('head coach')

    await page.goto('/players')
    await page
      .getByRole('button', { name: /view asha singh details/i })
      .click()
    await page.getByRole('button', { name: 'Edit Player' }).click()
    await expect(page.getByText('No account linked')).toBeVisible()
    await page.getByRole('button', { name: 'Link account' }).click()

    const dialog = page.getByRole('dialog', { name: 'Link player account' })
    await expect(dialog).toBeVisible()
    await dialog.getByRole('radio', { name: /Rohan Account/ }).check()
    await dialog.getByRole('button', { name: 'Link selected account' }).click()

    await expect(page.getByText('Rohan Account')).toBeVisible()
    await expect(page.getByText('rohan.player@example.com')).toBeVisible()
    await expect(page.getByText(/password|session|token/i)).toHaveCount(0)
    expect(api.accountAssociation.account?.id).toBe(
      '77777777-7777-4777-8777-777777777777',
    )
    expect(api.accountMutationRequests).toBe(1)
    expect(api.matchManagementRequests).toBe(0)
    await expect(page.getByText('Create match')).toHaveCount(0)
  })

  for (const viewport of viewports) {
    test(`preserves responsive, accessible dashboard behavior at ${viewport.label}`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport)
      await page.emulateMedia({ reducedMotion: 'reduce' })
      const auth = await installAuthApiMock(page)
      await installPlayersApiMock(page)
      const api = await installRoleAwareDashboardApiMock(page, auth)
      api.dashboardDelayMs = 1_500
      api.setRole('head coach')

      await page.goto('/')
      const loading = page.getByRole('status', { name: 'Loading dashboard' })
      await expect(loading).toBeVisible()
      const animationName = await loading
        .locator('[aria-hidden="true"]')
        .evaluate((element) => getComputedStyle(element).animationName)
      expect(animationName).toBe('none')

      const heading = page.getByRole('heading', {
        level: 1,
        name: 'Welcome back, Coach Asha',
      })
      await expect(heading).toBeVisible()
      const primaryAction = page.getByRole('link', { name: 'Schedule event' })
      await expectMinimumTarget(primaryAction)
      await primaryAction.focus()
      await expect(primaryAction).toBeFocused()

      const viewCalendar = page.getByRole('link', { name: 'View calendar' })
      await expectMinimumTarget(viewCalendar)
      await expect(
        page.getByRole('region', { name: 'Upcoming events' }),
      ).toBeVisible()
      await expect(
        page.getByRole('region', { name: 'Recent academy activity' }),
      ).toBeVisible()

      const summaryCards = page
        .getByRole('region', { name: 'Academy summary' })
        .locator('.dashboard-summary-card')
      const summaryCardBounds = await summaryCards.evaluateAll((cards) =>
        cards.map((card) => {
          const bounds = card.getBoundingClientRect()
          return { x: bounds.x, y: bounds.y, width: bounds.width }
        }),
      )
      expect(summaryCardBounds).toHaveLength(3)

      if (viewport.width === 768) {
        expect(summaryCardBounds[0]?.x).toBe(summaryCardBounds[1]?.x)
        expect(summaryCardBounds[1]?.y).toBeGreaterThan(
          summaryCardBounds[0]?.y ?? 0,
        )
        expect(summaryCardBounds[0]?.width).toBeGreaterThanOrEqual(400)
      }

      if (viewport.width === 1024) {
        expect(summaryCardBounds[0]?.y).toBe(summaryCardBounds[1]?.y)
        expect(summaryCardBounds[1]?.x).toBeGreaterThan(
          summaryCardBounds[0]?.x ?? 0,
        )
        expect(summaryCardBounds[2]?.y).toBeGreaterThan(
          summaryCardBounds[0]?.y ?? 0,
        )
        expect(summaryCardBounds[2]?.width).toBeGreaterThan(
          summaryCardBounds[0]?.width ?? 0,
        )
      }

      if (viewport.width === 1280 || viewport.width === 2560) {
        expect(summaryCardBounds[0]?.y).toBe(summaryCardBounds[1]?.y)
        expect(summaryCardBounds[1]?.x).toBeGreaterThan(
          summaryCardBounds[0]?.x ?? 0,
        )
      }

      expect(
        await page.evaluate(
          () =>
            document.documentElement.scrollWidth
            <= document.documentElement.clientWidth,
        ),
      ).toBe(true)

      if (viewport.width === 2560) {
        const dashboardBounds = await heading
          .locator('xpath=ancestor::div[contains(@class, "max-w-7xl")]')
          .boundingBox()
        expect(dashboardBounds).not.toBeNull()
        expect(dashboardBounds!.width).toBeLessThanOrEqual(1280)
        expect(dashboardBounds!.x).toBeGreaterThan(0)
      }
    })
  }
})
