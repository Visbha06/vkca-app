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

    await page.getByRole('searchbox', { name: 'Search players' }).fill('ash')
    await expect(page.getByText('Asha Singh')).toBeVisible()
    await expect(page.getByText('Maya Patel')).toHaveCount(0)
    expect(api.searches).toContain('ash')

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
    const closeDetails = page.getByRole('button', {
      name: 'Close player details',
    })
    const editPlayer = page.getByRole('button', { name: 'Edit Player' })
    await expect(closeDetails).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(editPlayer).toBeFocused()
    await page.keyboard.press('Shift+Tab')
    await expect(closeDetails).toBeFocused()
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
    ).toBeVisible()
    await expect(
      page.getByText('Asha Singh was updated successfully.'),
    ).toBeVisible()
    expect(api.updates).toBe(1)
    await page.getByRole('button', { name: 'Close player details' }).click()

    await page.getByRole('combobox', { name: 'Filter by team' }).selectOption('')
    await page.getByRole('searchbox', { name: 'Search players' }).fill('')
    await expect(page.getByText('Maya Patel')).toBeVisible()
    await page.getByRole('button', { name: 'Add Player' }).click()
    await page.getByRole('textbox', { name: 'First name' }).fill('Isha')
    await page.getByRole('textbox', { name: 'Last name' }).fill('Nair')
    await page.getByRole('button', { name: 'Date of birth' }).click()
    await page.getByRole('combobox', { name: 'Year' }).selectOption('2010')
    await page.getByRole('combobox', { name: 'Month' }).selectOption('2')
    await page
      .getByRole('gridcell', { name: 'Sunday, February 14, 2010' })
      .click()
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
    expect(
      api.players.find(({ first_name }) => first_name === 'Isha')
        ?.date_of_birth,
    ).toBe('2010-02-14')
    await page
      .getByRole('button', { name: /view isha nair details/i })
      .click()
    await expect(
      page.getByRole('dialog', { name: 'Isha Nair' }).getByText('14 Feb 2010'),
    ).toBeVisible()
    await page.getByRole('button', { name: 'Close player details' }).click()
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

    for (const width of [320, 390, 768, 1280, 1920]) {
      await page.setViewportSize({ width, height: 800 })
      await page.goto('/players')
      await page.getByRole('button', { name: 'Add Player' }).click()
      const trigger = page.getByRole('button', { name: 'Date of birth' })
      await trigger.click()
      const calendar = page.getByRole('dialog', {
        name: /Choose date of birth/,
      })
      const calendarBox = await calendar.boundingBox()
      expect(calendarBox).not.toBeNull()
      expect(calendarBox!.x).toBeGreaterThanOrEqual(0)
      expect(calendarBox!.x + calendarBox!.width).toBeLessThanOrEqual(width)
      expect(
        await page.evaluate(
          () =>
            document.documentElement.scrollWidth <=
            document.documentElement.clientWidth,
        ),
      ).toBe(true)
      const dayBox = await page
        .getByRole('gridcell', { name: /Today/ })
        .boundingBox()
      expect(dayBox?.height).toBeGreaterThanOrEqual(44)
      expect(dayBox?.width).toBeGreaterThanOrEqual(44)
      if (width === 320) {
        await page.getByRole('combobox', { name: 'Year' }).selectOption('2025')
        await page.getByRole('combobox', { name: 'Month' }).selectOption('7')
        const leadingDate = page.getByRole('gridcell', {
          name: 'Sunday, June 29, 2025',
        })
        const trailingDate = page.getByRole('gridcell', {
          name: 'Saturday, August 2, 2025',
        })
        const currentMonthDate = page.getByRole('gridcell', {
          name: 'Tuesday, July 1, 2025',
        })
        const [leadingStyle, trailingStyle, currentMonthStyle] =
          await Promise.all(
            [leadingDate, trailingDate, currentMonthDate].map((date) =>
              date.evaluate((element) => {
                const style = getComputedStyle(element)
                return {
                  backgroundColor: style.backgroundColor,
                  color: style.color,
                }
              }),
            ),
          )

        expect(leadingStyle).toEqual(trailingStyle)
        expect(leadingStyle.color).not.toBe(currentMonthStyle.color)
        expect(leadingStyle.backgroundColor).toBe(
          currentMonthStyle.backgroundColor,
        )
      }
      await page.keyboard.press('Escape')
      await expect(calendar).toBeHidden()
      await expect(trigger).toBeFocused()
      await page.getByRole('button', { name: 'Close Add Player' }).click()
    }
  })
})
