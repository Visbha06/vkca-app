// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClientError } from '@shared/api/client'
import DataQualityPage from './DataQualityPage'
import {
  applyDataQualityRemediation,
  fetchDataQuality,
} from '../api/dataQualityApi'

vi.mock('../api/dataQualityApi', () => ({
  applyDataQualityRemediation: vi.fn(),
  fetchDataQuality: vi.fn(),
}))

const finding = {
  finding_id: 'coach.inactive_assigned:coach:team',
  rule_id: 'coach.inactive_assigned' as const,
  severity: 'warning' as const,
  domain: 'coaches' as const,
  entity_type: 'coach_assignment' as const,
  entity_id: 'coach',
  entity_label: 'Alex Morgan — U13 Falcons',
  title: 'Inactive Assistant Coach remains assigned',
  explanation: 'The inactive assignment remains current.',
  recommended_action: 'Remove this one assignment.',
  direct_remediation: {
    action: 'remove_inactive_assistant_assignment' as const,
    coach_id: 'coach',
    team_id: 'team',
    expected_coach_version: 4,
    confirmation_required: true as const,
  },
  related_entities: [],
}

const populatedResponse = {
  findings: [finding],
  summary: {
    total_findings: 1,
    critical_count: 0,
    warning_count: 1,
    info_count: 0,
    domain_counts: {
      players: 0,
      teams: 0,
      rosters: 0,
      coaches: 1,
      calendar: 0,
    },
  },
  page: 1,
  page_size: 20,
  total_findings: 1,
  total_pages: 1,
  has_previous: false,
  has_next: false,
}

const resolvedResponse = {
  ...populatedResponse,
  findings: [],
  summary: {
    ...populatedResponse.summary,
    total_findings: 0,
    warning_count: 0,
    domain_counts: {
      ...populatedResponse.summary.domain_counts,
      coaches: 0,
    },
  },
  total_findings: 0,
  total_pages: 0,
}

function renderPage() {
  return render(
    <MemoryRouter>
      <DataQualityPage />
    </MemoryRouter>,
  )
}

async function openAndConfirm() {
  fireEvent.click(
    await screen.findByRole('button', { name: 'Remove assignment' }),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Confirm removal' }))
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Data Quality remediation', () => {
  it('confirms one typed action, refreshes, and announces success', async () => {
    vi.mocked(fetchDataQuality)
      .mockResolvedValueOnce(populatedResponse)
      .mockResolvedValueOnce(resolvedResponse)
    vi.mocked(applyDataQualityRemediation).mockResolvedValue({
      status: 'applied',
      action: 'remove_inactive_assistant_assignment',
      message: 'The inactive Assistant Coach assignment was removed.',
      affected_entity_id: 'coach',
      audit_action: 'coach.team_assignments_updated',
    })
    renderPage()

    await openAndConfirm()

    await waitFor(() =>
      expect(applyDataQualityRemediation).toHaveBeenCalledWith({
        finding_id: finding.finding_id,
        action: 'remove_inactive_assistant_assignment',
        coach_id: 'coach',
        team_id: 'team',
        expected_coach_version: 4,
        confirmed: true,
      }),
    )
    expect(
      await screen.findByText(
        'The inactive Assistant Coach assignment was removed.',
      ),
    ).toBeVisible()
    expect(await screen.findByText('No data quality issues found')).toBeVisible()
    await waitFor(() =>
      expect(screen.getByLabelText('Data quality results')).toHaveFocus(),
    )
    expect(fetchDataQuality).toHaveBeenCalledTimes(2)
  })

  it('retains the finding and hides server details after a safe failure', async () => {
    vi.mocked(fetchDataQuality).mockResolvedValue(populatedResponse)
    vi.mocked(applyDataQualityRemediation).mockRejectedValue(
      new ApiClientError(500, { detail: 'database constraint team_players_xyz' }),
    )
    renderPage()

    await openAndConfirm()

    expect(
      await screen.findByRole('alert'),
    ).toHaveTextContent('Unable to apply this remediation. No change was made.')
    expect(screen.queryByText(/team_players_xyz/)).not.toBeInTheDocument()
    expect(screen.getByText(finding.title)).toBeVisible()
    expect(screen.getByRole('dialog')).toBeVisible()
  })

  it('closes stale confirmation and re-evaluates after a conflict', async () => {
    vi.mocked(fetchDataQuality)
      .mockResolvedValueOnce(populatedResponse)
      .mockResolvedValueOnce(resolvedResponse)
    vi.mocked(applyDataQualityRemediation).mockRejectedValue(
      new ApiClientError(409, { detail: 'stale version' }),
    )
    renderPage()

    await openAndConfirm()

    expect(
      await screen.findByRole('alert'),
    ).toHaveTextContent(
      'This finding changed before the remediation was applied. Current findings were refreshed.',
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(await screen.findByText('No data quality issues found')).toBeVisible()
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Dismiss' })).toHaveFocus(),
    )
    expect(fetchDataQuality).toHaveBeenCalledTimes(2)
  })
})
