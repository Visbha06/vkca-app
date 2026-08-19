import { expect, test, type Page } from '@playwright/test'

interface PlayerMutationResponse {
  id: string
  bio: string | null
  version_number: number
}

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

interface JourneyResult {
  mutation: PlayerMutationResponse
  retrieval: RetrievalResponse
  mutationStatus: number
  retrievalStatus: number
}

const apiUrl = process.env.BACKGROUND_JOBS_E2E_API_URL
const authToken =
  process.env.BACKGROUND_JOBS_E2E_AUTH_TOKEN ?? 'e2e-head-coach-token'
const playerId =
  process.env.BACKGROUND_JOBS_E2E_PLAYER_ID ??
  '11111111-1111-4111-8111-111111111111'
const playerVersion = Number(
  process.env.BACKGROUND_JOBS_E2E_PLAYER_VERSION ?? '1',
)

async function installDeterministicBackgroundBoundary(
  page: Page,
  updatedBio: string,
) {
  let retrievalAttempts = 0
  await page.route(`**/api/v1/players/${playerId}`, async (route) => {
    const request = route.request()
    expect(request.method()).toBe('PUT')
    expect(request.headers().authorization).toBe(`Bearer ${authToken}`)
    expect(request.postDataJSON()).toEqual({
      bio: updatedBio,
      version_number: playerVersion,
    })
    await route.fulfill({
      status: 200,
      json: {
        id: playerId,
        first_name: 'Asha',
        last_name: 'Background',
        date_of_birth: '2012-03-02',
        bio: updatedBio,
        batting_style: 'right',
        bowling_style: 'right-arm medium',
        player_type: 'all-rounder',
        player_metadata: {},
        is_active: true,
        created_at: '2026-08-19T12:00:00Z',
        updated_at: '2026-08-19T12:01:00Z',
        version_number: playerVersion + 1,
        teams: [],
      },
    })
  })
  await page.route('**/api/v1/rag/retrieval?**', async (route) => {
    retrievalAttempts += 1
    const request = route.request()
    expect(request.method()).toBe('GET')
    expect(request.headers().authorization).toBe(`Bearer ${authToken}`)
    const current = retrievalAttempts >= 2
    await route.fulfill({
      status: 200,
      json: {
        results: current
          ? [
              {
                chunk_id: '22222222-2222-4222-8222-222222222222',
                document_id: '33333333-3333-4333-8333-333333333333',
                source_type: 'player_profile',
                source_key: playerId,
                text: updatedBio,
                score: 0.01,
                provenance: {
                  source_type: 'player_profile',
                  source_entity_id: playerId,
                },
              },
            ]
          : [],
        returned_count: current ? 1 : 0,
        limit: 10,
      } satisfies RetrievalResponse,
    })
  })
}

test('authorized mutation becomes visible through protected retrieval after background work', async ({
  page,
}) => {
  const updatedBio = `Background reconciliation ${Date.now()}`
  if (apiUrl === undefined) {
    await installDeterministicBackgroundBoundary(page, updatedBio)
  }
  await page.goto('/')

  const result = await page.evaluate(
    async ({ baseUrl, bearer, id, version, bio }): Promise<JourneyResult> => {
      const origin = baseUrl ?? window.location.origin
      const mutationResponse = await fetch(
        new URL(`/api/v1/players/${id}`, origin),
        {
          method: 'PUT',
          headers: {
            Authorization: `Bearer ${bearer}`,
            'Content-Type': 'application/json',
            'X-Request-ID': 'spec-013-background-reconciliation',
          },
          body: JSON.stringify({ bio, version_number: version }),
        },
      )
      const mutation = (await mutationResponse.json()) as PlayerMutationResponse
      let retrievalStatus = 0
      let retrieval: RetrievalResponse = {
        results: [],
        returned_count: 0,
        limit: 10,
      }
      for (let attempt = 0; attempt < 20; attempt += 1) {
        const url = new URL('/api/v1/rag/retrieval', origin)
        url.searchParams.set('query', bio)
        url.searchParams.set('limit', '10')
        const response = await fetch(url, {
          headers: { Authorization: `Bearer ${bearer}` },
        })
        retrievalStatus = response.status
        retrieval = (await response.json()) as RetrievalResponse
        if (
          retrieval.results.some(
            (item) => item.source_key === id && item.text.includes(bio),
          )
        ) {
          break
        }
        await new Promise((resolve) => window.setTimeout(resolve, 250))
      }
      return {
        mutation,
        retrieval,
        mutationStatus: mutationResponse.status,
        retrievalStatus,
      }
    },
    {
      baseUrl: apiUrl,
      bearer: authToken,
      id: playerId,
      version: playerVersion,
      bio: updatedBio,
    },
  )

  expect(result.mutationStatus).toBe(200)
  expect(result.mutation.id).toBe(playerId)
  expect(result.mutation.bio).toBe(updatedBio)
  expect(result.retrievalStatus).toBe(200)
  expect(result.retrieval.results).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        source_type: 'player_profile',
        source_key: playerId,
        text: expect.stringContaining(updatedBio),
      }),
    ]),
  )
  expect(JSON.stringify(result.retrieval)).not.toMatch(
    /embedding|vector|password|token|credential/i,
  )
})

