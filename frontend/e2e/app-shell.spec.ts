import { expect, test } from '@playwright/test'
import { installAuthApiMock } from './auth-api-mock'
import { installCalendarApiMock } from './calendar-api-mock'
import { installRoleAwareDashboardApiMock } from './role-aware-dashboard-fixtures'

test.describe('application shell primary journey', () => {
  test.beforeEach(async ({ page }) => {
    const auth = await installAuthApiMock(page)
    await installRoleAwareDashboardApiMock(page, auth)
  })

  test('navigates and collapses the inline sidebar at 1280px', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.goto('/')

    await expect(
      page.getByRole('heading', {
        level: 1,
        name: 'Welcome back, Coach John',
      }),
    ).toBeVisible()
    await expect(page.getByText('Academy Portal')).toBeVisible()
    await expect(page.getByRole('link', { name: 'Schedule event' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Create match' })).toHaveCount(0)
    await expect(page.getByRole('link', { name: 'Home' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    await page.evaluate(() => {
      document.body.dataset.navigationSession = 'preserved'
    })

    await page.getByRole('link', { name: 'Player Directory' }).click()
    await expect(page).toHaveURL(/\/players$/)
    await expect(page.locator('body')).toHaveAttribute(
      'data-navigation-session',
      'preserved',
    )
    await expect(
      page.getByRole('heading', { level: 1, name: 'Player Directory' }),
    ).toBeVisible()

    await page.getByRole('button', { name: 'Collapse sidebar' }).click()
    await expect(
      page.getByRole('button', { name: 'Expand sidebar' }),
    ).toHaveAttribute('aria-expanded', 'false')
    const collapsedSettings = page.getByRole('link', { name: 'User Settings' })
    const expandSidebar = page.getByRole('button', { name: 'Expand sidebar' })
    const [settingsBox, expandBox, sidebarBox] = await Promise.all([
      collapsedSettings.boundingBox(),
      expandSidebar.boundingBox(),
      page.getByLabel('Application sidebar').boundingBox(),
    ])
    expect(settingsBox).not.toBeNull()
    expect(expandBox).not.toBeNull()
    expect(sidebarBox).not.toBeNull()
    expect(settingsBox!.y).toBeLessThan(expandBox!.y)
    expect(expandBox!.x).toBeGreaterThanOrEqual(sidebarBox!.x)
    expect(expandBox!.x + expandBox!.width).toBeLessThanOrEqual(
      sidebarBox!.x + sidebarBox!.width,
    )
    await expect(
      page.getByRole('link', { name: 'Player Directory' }),
    ).toHaveAttribute('title', 'Player Directory')

    await page.getByRole('link', { name: 'Teams' }).click()
    await expect(page).toHaveURL(/\/teams$/)
    await expect(
      page.getByRole('heading', { level: 1, name: 'Teams' }),
    ).toBeVisible()
    await expect(page.getByRole('button', { name: 'Expand sidebar' })).toBeVisible()

    await page.getByRole('button', { name: 'Expand sidebar' }).focus()
    await page.keyboard.press('Enter')
    await expect(
      page.getByRole('button', { name: 'Collapse sidebar' }),
    ).toHaveAttribute('aria-expanded', 'true')
  })

  test('navigates with the overlay drawer at 375px', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/')

    const sidebar = page.getByLabel('Application sidebar')
    const backdrop = page.getByTestId('mobile-navigation-backdrop')

    await expect(sidebar).toBeHidden()
    await page.getByRole('button', { name: 'Open navigation menu' }).click()
    await expect(sidebar).toBeVisible()
    await expect(backdrop).toHaveAttribute('data-open', 'true')
    const closeNavigation = page.getByRole('button', {
      name: 'Close navigation menu',
    })
    await expect(closeNavigation).toBeFocused()
    await page.keyboard.press('Shift+Tab')
    await expect(page.getByRole('button', { name: 'Log out' })).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(closeNavigation).toBeFocused()

    await page.getByRole('link', { name: 'Teams' }).click()
    await expect(page).toHaveURL(/\/teams$/)
    await expect(
      page.getByRole('heading', { level: 1, name: 'Teams' }),
    ).toBeVisible()
    await expect(page.getByRole('heading', { level: 1, name: 'Teams' })).toBeFocused()
    await expect(page).toHaveTitle('Teams | VK Cricket Academy')
    await expect(sidebar).toBeHidden()

    await page.getByRole('button', { name: 'Open navigation menu' }).click()
    await expect(sidebar).toBeVisible()
    await backdrop.click({ position: { x: 350, y: 400 } })
    await expect(sidebar).toBeHidden()

    const hasHorizontalOverflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
    )
    expect(hasHorizontalOverflow).toBe(false)
  })

  test('renders implemented routes and the recoverable 404 page', async ({
    page,
  }) => {
    await page.goto('/players')
    await expect(
      page.getByRole('heading', { level: 1, name: 'Player Directory' }),
    ).toBeVisible()
    await expect(
      page.getByText('This section will be available in a future update.'),
    ).toHaveCount(0)

    await page.goto('/teams')
    await expect(
      page.getByRole('heading', { level: 1, name: 'Teams' }),
    ).toBeVisible()
    await expect(
      page.getByText('This section will be available in a future update.'),
    ).toHaveCount(0)

    await page.goto('/coaches')
    await expect(
      page.getByRole('heading', { level: 1, name: 'Coaches Portal' }),
    ).toBeVisible()
    await expect(
      page.getByText('This section will be available in a future update.'),
    ).toHaveCount(0)
    await expect(
      page.getByRole('combobox', { name: 'Coach status' }),
    ).toBeVisible()
    await expect(page.getByRole('button', { name: 'Add Coach' })).toBeVisible()

    await installCalendarApiMock(page)
    await page.goto('/calendar')
    await expect(
      page.getByRole('heading', { level: 1, name: 'Calendar' }),
    ).toBeVisible()
    await expect(
      page.getByText('This section will be available in a future update.'),
    ).toHaveCount(0)
    await expect(page.getByRole('grid', { name: /calendar$/ })).toBeVisible()
    await expect(page.getByRole('heading', { level: 2, name: 'Today' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Create Event' })).toBeVisible()

    await page.goto('/settings')
    await expect(page.getByRole('dialog', { name: 'User Settings' })).toBeVisible()

    await page.goto('/nonexistent-route')
    await expect(
      page.getByRole('heading', { level: 1, name: 'Page Not Found' }),
    ).toBeVisible()
    await expect(page.getByLabel('Application sidebar')).toBeVisible()
    await page.getByRole('link', { name: 'Home' }).click()
    await expect(page).toHaveURL(/\/$/)
  })

  test('adapts without overflow from mobile through desktop widths', async ({
    page,
  }) => {
    for (const width of [320, 768, 1024, 1440, 1920]) {
      await page.setViewportSize({ width, height: 800 })
      await page.goto('/')

      const hasHorizontalOverflow = await page.evaluate(
        () =>
          document.documentElement.scrollWidth >
          document.documentElement.clientWidth,
      )
      expect(hasHorizontalOverflow).toBe(false)

      if (width < 768) {
        await expect(page.getByLabel('Application sidebar')).toBeHidden()
        await expect(
          page.getByRole('button', { name: 'Open navigation menu' }),
        ).toBeVisible()
      } else {
        await expect(page.getByLabel('Application sidebar')).toBeVisible()
        await expect(
          page.getByRole('button', { name: 'Open navigation menu' }),
        ).toBeHidden()
      }
    }
  })

  test('exposes accessible state and honors reduced motion', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/')

    await expect(page.locator('h1')).toHaveCount(1)
    await expect(page.getByText('Academy Portal')).toBeVisible()
    await expect(page.getByRole('link', { name: 'Home' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    await expect(page.getByLabel('Application sidebar')).toHaveCSS(
      'transition-duration',
      '0s',
    )

    await page.keyboard.press('Tab')
    const skipLink = page.getByRole('link', { name: 'Skip to main content' })
    await expect(skipLink).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.getByRole('main')).toBeFocused()

    const focusedLink = page.getByRole('link', { name: 'Home' })
    await focusedLink.focus()
    await expect(focusedLink).toBeFocused()
    const focusShadow = await focusedLink.evaluate(
      (element) => getComputedStyle(element).boxShadow,
    )
    expect(focusShadow).not.toBe('none')

    const toggle = page.getByRole('button', { name: 'Collapse sidebar' })
    await expect(toggle).toHaveAttribute('aria-expanded', 'true')
  })
})
