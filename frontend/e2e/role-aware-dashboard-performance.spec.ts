import { expect, test, type Page } from '@playwright/test'
import { performance } from 'node:perf_hooks'
import { installAuthApiMock } from './auth-api-mock'
import { installPlayersApiMock } from './players-api-mock'
import { installRoleAwareDashboardApiMock } from './role-aware-dashboard-fixtures'

const warmupNavigations = 10
const measuredNavigations = 100
const maximumP95Milliseconds = 2_000

async function openPopulatedDashboard(page: Page) {
  const startedAt = performance.now()
  await page.goto('/')
  await expect(
    page.getByRole('heading', {
      level: 1,
      name: 'Welcome back, Coach Asha',
    }),
  ).toBeVisible()
  const summary = page.getByRole('region', { name: 'Academy summary' })
  await expect(summary).toContainText('Batting fundamentals')
  await expect(summary).toContainText('Northside CC')
  await expect(summary).toContainText('42')
  await expect(
    page.getByRole('region', { name: 'Upcoming events' }).getByRole('listitem'),
  ).toHaveCount(5)
  await expect(
    page
      .getByRole('region', { name: 'Recent academy activity' })
      .getByRole('listitem'),
  ).toHaveCount(4)
  return performance.now() - startedAt
}

test('keeps the deterministic local populated dashboard p95 at or below two seconds', async ({
  page,
}) => {
  test.setTimeout(180_000)
  const auth = await installAuthApiMock(page)
  await installPlayersApiMock(page)
  const api = await installRoleAwareDashboardApiMock(page, auth)
  api.setRole('head coach')

  for (let index = 0; index < warmupNavigations; index += 1) {
    await openPopulatedDashboard(page)
  }

  const durations: number[] = []
  for (let index = 0; index < measuredNavigations; index += 1) {
    durations.push(await openPopulatedDashboard(page))
  }

  durations.sort((left, right) => left - right)
  const p95Index = Math.ceil(durations.length * 0.95) - 1
  const p95 = durations[p95Index]
  expect(p95, `local mocked dashboard p95 was ${p95?.toFixed(1)} ms`).toBeLessThanOrEqual(
    maximumP95Milliseconds,
  )
  expect(api.dashboardRequests).toBeGreaterThanOrEqual(
    warmupNavigations + measuredNavigations,
  )
})
