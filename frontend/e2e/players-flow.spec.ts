import { expect, test } from '@playwright/test'
import { installAuthApiMock } from './auth-api-mock'
import { installPlayersApiMock } from './players-api-mock'

test.describe('players interface', () => {
  test('logs in, filters, views details, edits, and creates as a coach', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await installAuthApiMock(page, false)
    const api = await installPlayersApiMock(page)

    await page.goto('/players')
    await expect(page).toHaveURL(/\/login\?redirect=%2Fplayers$/)
    await page.getByLabel('Email address').fill('john.coach@vkca.test')
    await page.getByLabel('Password', { exact: true }).fill('CoachP@ssword1')
    await page.getByRole('button', { name: 'Log in' }).click()
    await expect(page).toHaveURL(/\/players$/)
    await expect(
      page.getByRole('heading', { name: 'Player Directory' }),
    ).toBeVisible()

    await page.getByRole('combobox', { name: 'Filter by team' }).selectOption(
      'team-junior',
    )
    await expect(page.getByText('Asha Singh')).toBeVisible()
    await expect(page.getByText('Maya Patel')).toHaveCount(0)
    expect(api.filters).toContain('team-junior')

    await page.getByRole('button', { name: /view asha singh details/i }).click()
    await expect(
      page.getByRole('dialog', { name: 'Asha Singh' }),
    ).toBeVisible()
    await page.getByRole('button', { name: 'Edit Player' }).click()
    await expect(
      page.getByRole('dialog', { name: 'Edit Asha Singh' }),
    ).toBeVisible()
    await page.getByRole('textbox', { name: /^Bio/ }).fill(
      'Opening batter and vice-captain',
    )
    await page.getByRole('button', { name: 'Save changes' }).click()
    await expect(
      page.getByText('Opening batter and vice-captain'),
    ).toHaveCount(0)
    await expect(
      page.getByText('Asha Singh was updated successfully.'),
    ).toBeVisible()
    expect(api.updates).toBe(1)
    await page.getByRole('button', { name: 'Close player details' }).click()

    await page.getByRole('combobox', { name: 'Filter by team' }).selectOption('')
    await page.getByRole('button', { name: 'Add Player' }).click()
    await page.getByRole('textbox', { name: 'First name' }).fill('Isha')
    await page.getByRole('textbox', { name: 'Last name' }).fill('Nair')
    await page.getByLabel('Date of birth').fill('2010-02-14')
    await page.getByRole('combobox', { name: 'Batting style' }).selectOption(
      'left',
    )
    await page.getByRole('combobox', { name: 'Bowling style' }).selectOption(
      'left-arm orthodox',
    )
    await page.getByRole('combobox', { name: 'Player type' }).selectOption(
      'all-rounder',
    )
    await page.getByRole('button', { name: 'Create player' }).click()

    await expect(
      page.getByText('Isha Nair was added successfully.'),
    ).toBeVisible()
    await expect(
      page.getByRole('button', { name: /view isha nair details/i }),
    ).toBeVisible()
    expect(api.creates).toBe(1)
  })

  test('reflows without horizontal overflow at mobile and desktop widths', async ({
    page,
  }) => {
    await installAuthApiMock(page)
    await installPlayersApiMock(page)

    for (const [width, expectedColumns] of [
      [320, 1],
      [1280, 3],
    ] as const) {
      await page.setViewportSize({ width, height: 800 })
      await page.goto('/players')
      const playerGrid = page.getByRole('list', { name: 'Players' })
      await expect(playerGrid).toBeVisible()

      const columnCount = await playerGrid.evaluate((element) =>
        getComputedStyle(element).gridTemplateColumns.split(' ').length,
      )
      expect(columnCount).toBe(expectedColumns)
      expect(
        await page.evaluate(
          () =>
            document.documentElement.scrollWidth <=
            document.documentElement.clientWidth,
        ),
      ).toBe(true)

      const addButtonBox = await page
        .getByRole('button', { name: 'Add Player' })
        .boundingBox()
      expect(addButtonBox?.height).toBeGreaterThanOrEqual(44)
      expect(addButtonBox?.width).toBeGreaterThanOrEqual(44)

      await page
        .getByRole('button', { name: /view asha singh details/i })
        .click()
      const detailsDialog = page.getByRole('dialog', { name: 'Asha Singh' })
      const dialogBox = await detailsDialog.boundingBox()
      expect(dialogBox).not.toBeNull()
      expect(dialogBox!.x).toBeGreaterThanOrEqual(0)
      expect(dialogBox!.x + dialogBox!.width).toBeLessThanOrEqual(width)
      await page.getByRole('button', { name: 'Close player details' }).click()
    }
  })
})
