import { expect, test } from '@playwright/test'
import { installAuthApiMock } from './auth-api-mock'

const validPassword = 'NewP@ssword!2026'

test.describe('frontend authentication quickstart', () => {
  test('covers login, restoration, protected navigation, settings, password change, and logout', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    const api = await installAuthApiMock(page, false)

    await page.goto('/players')
    await expect(page).toHaveURL(/\/login\?redirect=%2Fplayers$/)
    await expect(page.getByRole('heading', { name: 'Sign in to your account' })).toBeVisible()
    await expect(page.getByLabel('Application sidebar')).toHaveCount(0)

    await page.getByRole('button', { name: 'Log in' }).click()
    await expect(page.getByText('Email is required.')).toBeVisible()
    await expect(page.getByText('Password is required.')).toBeVisible()

    await page.getByLabel('Email address').fill('john.coach@vkca.test')
    await page.getByLabel('Password', { exact: true }).fill('wrong-password')
    await page.getByRole('button', { name: 'Show password' }).click()
    await expect(page.getByLabel('Password', { exact: true })).toHaveAttribute('type', 'text')
    await page.getByRole('button', { name: 'Hide password' }).click()
    api.nextLoginStatus = 401
    await page.getByRole('button', { name: 'Log in' }).click()
    await expect(page.getByRole('alert')).toHaveText('Invalid email or password.')
    await expect(page.getByText('Invalid credentials')).toHaveCount(0)

    await page.getByLabel('Password', { exact: true }).fill(validPassword)
    await page.getByRole('button', { name: 'Log in' }).click()
    await expect(page).toHaveURL(/\/players$/)
    await expect(page.getByRole('heading', { name: 'Player Directory' })).toBeVisible()

    await page.reload()
    await expect(page).toHaveURL(/\/players$/)
    await expect(page.getByRole('heading', { name: 'Player Directory' })).toBeVisible()
    await page.goto('/login')
    await expect(page).toHaveURL(/\/$/)
    await page.getByRole('link', { name: 'Teams' }).click()
    await expect(page.getByRole('heading', { name: 'Teams' })).toBeVisible()

    await page.getByRole('link', { name: 'User Settings' }).click()
    const dialog = page.getByRole('dialog', { name: 'User Settings' })
    await expect(dialog).toBeVisible()
    await expect(page.getByLabel('Email address')).toHaveValue('john.coach@vkca.test')
    await expect(page.getByLabel('Email address')).toHaveAttribute('readonly', '')
    await expect(page.getByLabel('Role')).toHaveValue('Head coach')
    await expect(page.getByLabel('Role')).toHaveAttribute('readonly', '')

    await page.getByLabel('First name').fill('Asha')
    await page.getByLabel('Last name').fill('Rao')
    await page.getByRole('button', { name: 'Save profile' }).click()
    await expect(page.getByText('Your profile has been updated.')).toBeVisible()
    expect(api.profileUpdates).toBe(1)
    expect(api.user.first_name).toBe('Asha')

    await page.getByLabel('New password', { exact: true }).fill('short')
    await page.getByLabel('Confirm new password', { exact: true }).fill('different')
    await page.getByRole('button', { name: 'Change password' }).click()
    await expect(page.getByText('Password must be at least 12 characters.')).toBeVisible()
    await expect(page.getByText('Passwords must match.')).toBeVisible()

    await page.getByLabel('New password', { exact: true }).fill(validPassword)
    await page.getByLabel('Confirm new password', { exact: true }).fill(validPassword)
    await page.getByRole('button', { name: 'Change password' }).click()
    await expect(page).toHaveURL(/\/login\?reason=password-changed$/)
    await expect(page.getByText('Your password was changed. Please sign in again.')).toBeVisible()
    expect(api.passwordChanges).toBe(1)
    expect(api.logouts).toBe(1)

    await page.getByLabel('Email address').fill('john.coach@vkca.test')
    await page.getByLabel('Password', { exact: true }).fill(validPassword)
    await page.getByRole('button', { name: 'Log in' }).click()
    await expect(page).toHaveURL(/\/$/)
    await page.getByRole('button', { name: 'Log out' }).click()
    await expect(page).toHaveURL(/\/login(?:\?redirect=%2F)?$/)
    await expect(page.getByLabel('Application sidebar')).toHaveCount(0)
    expect(api.logouts).toBe(2)
  })

  test('traps focus and closes account settings with Escape or the backdrop', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await installAuthApiMock(page)
    await page.goto('/')

    const settingsTrigger = page.getByRole('link', { name: 'User Settings' })
    await settingsTrigger.click()
    await expect(page.getByLabel('First name')).toBeFocused()
    await page.keyboard.press('Shift+Tab')
    await expect(page.getByRole('button', { name: 'Close account settings' })).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(page.getByLabel('First name')).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(page).toHaveURL(/\/$/)
    await expect(settingsTrigger).toBeFocused()

    await settingsTrigger.click()
    await page.getByTestId('account-settings-backdrop').click({ position: { x: 4, y: 4 } })
    await expect(page).toHaveURL(/\/$/)
    await expect(page.getByRole('dialog')).toHaveCount(0)
  })

  test('keeps login and settings usable at every required viewport', async ({ page }, testInfo) => {
    const api = await installAuthApiMock(page, false)
    for (const width of [320, 768, 1280, 2560]) {
      await page.setViewportSize({ width, height: 640 })
      api.authenticated = false
      await page.goto('/login')
      await expect(page.getByRole('heading', { name: 'Sign in to your account' })).toBeVisible()

      const loginControls = [
        page.getByLabel('Email address'),
        page.getByLabel('Password', { exact: true }),
        page.getByRole('button', { name: 'Show password' }),
        page.getByRole('button', { name: 'Log in' }),
      ]
      for (const control of loginControls) {
        const box = await control.boundingBox()
        expect(box?.height).toBeGreaterThanOrEqual(44)
        expect(box?.width).toBeGreaterThanOrEqual(44)
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`login-${width}.png`) })

      api.authenticated = true
      await page.goto('/settings')
      const dialog = page.getByRole('dialog', { name: 'User Settings' })
      await expect(dialog).toBeVisible()
      const dialogBox = await dialog.boundingBox()
      expect(dialogBox).not.toBeNull()
      expect(dialogBox!.x).toBeGreaterThanOrEqual(0)
      expect(dialogBox!.x + dialogBox!.width).toBeLessThanOrEqual(width)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)

      for (const control of [
        page.getByLabel('First name'),
        page.getByLabel('New password', { exact: true }),
        page.getByRole('button', { name: 'Show new password' }),
        page.getByRole('button', { name: 'Close account settings' }),
        page.getByRole('button', { name: 'Save profile' }),
        page.getByRole('button', { name: 'Change password' }),
      ]) {
        const box = await control.boundingBox()
        expect(box?.height).toBeGreaterThanOrEqual(44)
        expect(box?.width).toBeGreaterThanOrEqual(44)
      }

      const scrollState = await dialog.evaluate((element) => ({
        clientHeight: element.clientHeight,
        overflowY: getComputedStyle(element).overflowY,
        scrollHeight: element.scrollHeight,
      }))
      expect(scrollState.overflowY).toBe('auto')
      await page.screenshot({ path: testInfo.outputPath(`settings-${width}.png`) })
      if (scrollState.scrollHeight > scrollState.clientHeight) {
        await dialog.evaluate((element) => { element.scrollTop = element.scrollHeight })
        expect(await dialog.evaluate((element) => element.scrollTop)).toBeGreaterThan(0)
        await page.screenshot({ path: testInfo.outputPath(`settings-${width}-scrolled.png`) })
      }
    }
  })
})
