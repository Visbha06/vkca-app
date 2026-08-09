// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import DataQualityPage from './DataQualityPage'
import { fetchDataQuality } from '../api/dataQualityApi'

vi.mock('../api/dataQualityApi', () => ({ fetchDataQuality: vi.fn() }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('DataQualityPage', () => {
  it('shows the unfiltered summary and a finding explanation', async () => {
    vi.mocked(fetchDataQuality).mockResolvedValue({
      findings: [{ finding_id: 'player.active_unassigned:1', rule_id: 'player.active_unassigned', severity: 'warning', domain: 'players', entity_type: 'player', entity_id: '1', entity_label: 'Asha Patel', title: 'Active player is not assigned to a team', explanation: 'Asha is active but has no roster.', recommended_action: 'Review the player in Teams.', direct_remediation: null, related_entities: [] }],
      summary: { total_findings: 1, critical_count: 0, warning_count: 1, info_count: 0, domain_counts: { players: 1, teams: 0, rosters: 0, coaches: 0, calendar: 0 } },
      page: 1, page_size: 20, total_findings: 1, total_pages: 1, has_previous: false, has_next: false,
    })

    render(<MemoryRouter><DataQualityPage /></MemoryRouter>)

    expect(await screen.findByRole('heading', { name: 'Data Quality' })).toBeVisible()
    expect(screen.getByText('Asha is active but has no roster.')).toBeVisible()
    expect(screen.getByRole('status')).toHaveTextContent('1 finding shown')
  })

  it('shows the explicit healthy state after an empty response', async () => {
    vi.mocked(fetchDataQuality).mockResolvedValue({
      findings: [],
      summary: { total_findings: 0, critical_count: 0, warning_count: 0, info_count: 0, domain_counts: { players: 0, teams: 0, rosters: 0, coaches: 0, calendar: 0 } },
      page: 1, page_size: 20, total_findings: 0, total_pages: 0, has_previous: false, has_next: false,
    })

    render(<MemoryRouter><DataQualityPage /></MemoryRouter>)

    expect(await screen.findByText('No data quality issues found')).toBeVisible()
  })
})
