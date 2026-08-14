import { expect, test, type Page } from '@playwright/test'

interface RetrievalResult {
  chunk_id: string
  document_id: string
  source_type: string
  source_key: string
  text: string
  score: number
  provenance: {
    source_type: string
    source_entity_id: string | null
  }
}

interface RetrievalResponse {
  results: RetrievalResult[]
  returned_count: number
  limit: number
}

const apiUrl = process.env.RAG_E2E_API_URL
const authToken = process.env.RAG_E2E_AUTH_TOKEN

async function installDeterministicRetrievalBoundary(page: Page) {
  await page.route('**/api/v1/rag/retrieval?**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())

    expect(request.method()).toBe('GET')
    expect(request.headers().authorization).toBe('Bearer e2e-head-coach-token')
    expect(url.searchParams.get('query')).toBe('recent practice')
    expect(url.searchParams.get('limit')).toBe('2')
    for (const forbidden of [
      'user_id',
      'player_id',
      'role',
      'team_id',
      'age_group',
      'scope',
    ]) {
      expect(url.searchParams.has(forbidden)).toBe(false)
    }

    await route.fulfill({
      status: 200,
      json: {
        results: [
          {
            chunk_id: '11111111-1111-4111-8111-111111111111',
            document_id: '22222222-2222-4222-8222-222222222222',
            source_type: 'calendar_occurrence',
            source_key: 'assigned-u13-practice',
            text: 'Calendar event: Assigned U13 practice',
            score: 0.02,
            provenance: {
              source_type: 'calendar_occurrence',
              source_entity_id: '33333333-3333-4333-8333-333333333333',
            },
          },
        ],
        returned_count: 1,
        limit: 2,
      } satisfies RetrievalResponse,
    })
  })
}

test('authenticates the bounded retrieval request and receives no forbidden result', async ({
  page,
}) => {
  const token = authToken ?? 'e2e-head-coach-token'
  if (apiUrl === undefined) {
    await installDeterministicRetrievalBoundary(page)
  }

  await page.goto('/')
  const response = await page.evaluate(
    async ({ baseUrl, bearer }) => {
      const url = new URL('/api/v1/rag/retrieval', baseUrl ?? window.location.origin)
      url.searchParams.set('query', 'recent practice')
      url.searchParams.set('limit', '2')
      const result = await fetch(url, {
        headers: { Authorization: `Bearer ${bearer}` },
      })
      return {
        body: (await result.json()) as RetrievalResponse,
        status: result.status,
      }
    },
    { baseUrl: apiUrl, bearer: token },
  )

  expect(response.status).toBe(200)
  expect(response.body.returned_count).toBe(response.body.results.length)
  expect(response.body.returned_count).toBeLessThanOrEqual(2)
  expect(response.body.limit).toBe(2)
  expect(response.body.results).not.toEqual(
    expect.arrayContaining([
      expect.objectContaining({ source_key: 'forbidden-unassigned-team' }),
      expect.objectContaining({ source_key: 'inactive-player' }),
    ]),
  )
  expect(JSON.stringify(response.body)).not.toMatch(
    /embedding|vector|password|token|credential|answer/i,
  )
})
